using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Reports what every imported model really contains: hierarchy, pivots, empties, bounds and, for
    /// road tiles, which cell edges the asphalt reaches (to confirm openings after axis conversion).
    /// </summary>
    public static class ModelInspector
    {
        public const string ModelsRoot = "Assets/Skyfold/Art/Models";

        [MenuItem("SKYFOLD/Dev/Inspect Models")]
        public static void InspectMenu() => Inspect("Logs/models_report.txt");

        public static void BatchInspect()
        {
            Inspect("Logs/models_report.txt");
            EditorApplication.Exit(0);
        }

        /// <summary>Per-mesh detail for a few models: vertex colours and the normals of the lowest vertices.</summary>
        public static void BatchMeshDetail()
        {
            var sb = new StringBuilder();
            foreach (var name in new[] { "Sky/cloud_puff_a", "Sky/storm_cloud", "Buildings/bldg_substation" })
            {
                var go = AssetDatabase.LoadAssetAtPath<GameObject>($"{ModelsRoot}/{name}.fbx");
                if (go == null) { sb.AppendLine("missing " + name); continue; }
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                {
                    var m = mf.sharedMesh;
                    if (m == null) continue;
                    var v = m.vertices; var n = m.normals; var c = m.colors;
                    sb.AppendLine($"== {name}/{mf.name} verts={v.Length} subMeshes={m.subMeshCount} colours={c.Length} mats={string.Join(",", mf.GetComponent<Renderer>().sharedMaterials.Select(x => x != null ? x.name : "null"))}");
                    if (c.Length > 0)
                    {
                        sb.AppendLine($"   colour r {c.Min(x => x.r):0.00}..{c.Max(x => x.r):0.00} g {c.Min(x => x.g):0.00}..{c.Max(x => x.g):0.00} b {c.Min(x => x.b):0.00}..{c.Max(x => x.b):0.00} a {c.Min(x => x.a):0.00}..{c.Max(x => x.a):0.00}");
                    }
                    float minY = v.Min(p => p.y);
                    var low = Enumerable.Range(0, v.Length).Where(i => v[i].y < minY + 0.05f * (v.Max(p => p.y) - minY)).ToList();
                    Vector3 avgN = Vector3.zero; foreach (var i in low) avgN += n[i];
                    sb.AppendLine($"   lowest {low.Count} verts: avg normal {F(avgN.normalized)}; sample normals {string.Join(" ", low.Take(6).Select(i => F(n[i])))}");
                    if (c.Length > 0) sb.AppendLine($"   lowest colours {string.Join(" ", low.Take(6).Select(i => $"({c[i].r:0.00},{c[i].g:0.00},{c[i].b:0.00})"))}");
                }
            }
            File.WriteAllText("Logs/mesh_detail.txt", sb.ToString());
            EditorApplication.Exit(0);
        }

        public static void Inspect(string outPath)
        {
            var sb = new StringBuilder();
            var guids = AssetDatabase.FindAssets("t:Model", new[] { ModelsRoot });
            foreach (var g in guids.Select(AssetDatabase.GUIDToAssetPath).OrderBy(p => p))
            {
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(g);
                if (go == null) continue;
                var b = Bounds(go);
                int tris = go.GetComponentsInChildren<MeshFilter>(true).Where(m => m.sharedMesh != null).Sum(m => m.sharedMesh.triangles.Length / 3);
                sb.AppendLine($"== {g}  tris={tris}  bounds center={F(b.center)} size={F(b.size)}");
                Walk(go.transform, go.transform, 1, sb);
                var mats = go.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Select(m => m.name).Distinct();
                sb.AppendLine("   materials: " + string.Join(", ", mats));
                bool hasColors = go.GetComponentsInChildren<MeshFilter>(true).Any(m => m.sharedMesh != null && m.sharedMesh.colors32 != null && m.sharedMesh.colors32.Length > 0);
                sb.AppendLine("   vertex colours: " + hasColors);
                var road = SubmeshBounds(go, "SKY_Road");
                if (road.HasValue) sb.AppendLine($"   SKY_Road bounds min={F(road.Value.min)} max={F(road.Value.max)} -> edges {Edges(road.Value)}");
            }
            Directory.CreateDirectory(Path.GetDirectoryName(outPath));
            File.WriteAllText(outPath, sb.ToString());
            Debug.Log("[SKYFOLD] Model report: " + outPath + " (" + guids.Length + " models)");
        }

        static string F(Vector3 v) => $"({v.x:0.##}, {v.y:0.##}, {v.z:0.##})";

        static void Walk(Transform root, Transform t, int depth, StringBuilder sb)
        {
            foreach (Transform c in t)
            {
                var mf = c.GetComponent<MeshFilter>();
                Vector3 p = root.InverseTransformPoint(c.position);
                string kind = mf != null ? "mesh" : "empty";
                sb.AppendLine($"{new string(' ', depth * 2)}- {c.name} [{kind}] pos={F(p)} rot={F(c.localEulerAngles)} scale={F(c.localScale)}");
                Walk(root, c, depth + 1, sb);
            }
        }

        public static Bounds Bounds(GameObject go)
        {
            var rs = go.GetComponentsInChildren<MeshFilter>(true);
            bool init = false;
            var b = new Bounds();
            foreach (var mf in rs)
            {
                if (mf.sharedMesh == null) continue;
                var mb = mf.sharedMesh.bounds;
                var m = go.transform.worldToLocalMatrix * mf.transform.localToWorldMatrix;
                for (int i = 0; i < 8; i++)
                {
                    var corner = mb.center + Vector3.Scale(mb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    var w = m.MultiplyPoint3x4(corner);
                    if (!init) { b = new Bounds(w, Vector3.zero); init = true; } else b.Encapsulate(w);
                }
            }
            return b;
        }

        /// <summary>Bounds of all triangles that use a material whose name starts with the given name.</summary>
        public static Bounds? SubmeshBounds(GameObject go, string material)
        {
            bool init = false;
            var b = new Bounds();
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mesh = mf.sharedMesh;
                var verts = mesh.vertices;
                var m = go.transform.worldToLocalMatrix * mf.transform.localToWorldMatrix;
                for (int s = 0; s < mesh.subMeshCount && s < r.sharedMaterials.Length; s++)
                {
                    var mat = r.sharedMaterials[s];
                    if (mat == null || !mat.name.StartsWith(material)) continue;
                    foreach (var idx in mesh.GetTriangles(s))
                    {
                        var w = m.MultiplyPoint3x4(verts[idx]);
                        if (!init) { b = new Bounds(w, Vector3.zero); init = true; } else b.Encapsulate(w);
                    }
                }
            }
            return init ? b : (Bounds?)null;
        }

        static string Edges(Bounds road)
        {
            var e = new List<string>();
            if (road.max.z > 7.6f) e.Add("N");
            if (road.max.x > 7.6f) e.Add("E");
            if (road.min.z < -7.6f) e.Add("S");
            if (road.min.x < -7.6f) e.Add("W");
            return string.Join(",", e);
        }
    }
}
