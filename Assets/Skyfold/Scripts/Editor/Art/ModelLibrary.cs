using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Finds imported models by name and instantiates them with the shared palette materials.
    /// Missing models get a clearly named, palette-coloured placeholder so the scene always builds.
    /// </summary>
    public static class ModelLibrary
    {
        static Dictionary<string, string> s_Index;
        public static readonly List<string> Missing = new List<string>();

        public static void Refresh()
        {
            s_Index = new Dictionary<string, string>();
            foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { ModelInspector.ModelsRoot }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                s_Index[System.IO.Path.GetFileNameWithoutExtension(path)] = path;
            }
            Missing.Clear();
        }

        public static bool Has(string name)
        {
            if (s_Index == null) Refresh();
            return s_Index.ContainsKey(name);
        }

        public static GameObject Prefab(string name)
        {
            if (s_Index == null) Refresh();
            return s_Index.TryGetValue(name, out var p) ? AssetDatabase.LoadAssetAtPath<GameObject>(p) : null;
        }

        /// <summary>Instantiates a model under parent at a local pose. Never returns null.</summary>
        public static GameObject Spawn(string name, Transform parent, Vector3 localPos, float yaw = 0f, float scale = 1f)
        {
            var prefab = Prefab(name);
            GameObject go;
            if (prefab != null)
            {
                go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
                RemapMaterials(go);
            }
            else
            {
                if (!Missing.Contains(name)) Missing.Add(name);
                go = Placeholder(name);
                go.transform.SetParent(parent, false);
            }
            go.name = name;
            go.transform.localPosition = localPos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            go.transform.localScale = Vector3.one * scale;
            return go;
        }

        public static string CleanMaterialName(string n)
        {
            if (string.IsNullOrEmpty(n)) return n;
            n = n.Replace(" (Instance)", "");
            int dot = n.IndexOf('.');
            if (dot > 0) n = n.Substring(0, dot);
            return n.Trim();
        }

        public static void RemapMaterials(GameObject go)
        {
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    string n = CleanMaterialName(mats[i] != null ? mats[i].name : "SKY_Pearl");
                    var lib = MaterialLibrary.TryGet(n) ?? MaterialLibrary.Get("SKY_Pearl");
                    if (mats[i] != lib) { mats[i] = lib; changed = true; }
                }
                if (changed) r.sharedMaterials = mats;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            }
        }

        public static void SetMaterial(GameObject go, string material)
        {
            var m = MaterialLibrary.Get(material);
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++) mats[i] = m;
                r.sharedMaterials = mats;
            }
        }

        // ------------------------------------------------------------------ placeholders
        static GameObject Box(string name, Vector3 size, Vector3 center, string mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.localScale = size;
            go.transform.localPosition = center;
            SetMaterial(go, mat);
            WhiteColors(go);
            return go;
        }

        static void WhiteColors(GameObject go)
        {
            // Primitives have no vertex colours; give them white so the AO term is neutral.
            var mf = go.GetComponent<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) return;
            var key = "Skyfold_" + mf.sharedMesh.name;
            var mesh = Object.Instantiate(mf.sharedMesh);
            mesh.name = key;
            var c = new Color32[mesh.vertexCount];
            for (int i = 0; i < c.Length; i++) c[i] = new Color32(255, 255, 255, 255);
            mesh.colors32 = c;
            mf.sharedMesh = PlaceholderMeshes.Store(key, mesh);
        }

        static GameObject Placeholder(string name)
        {
            var root = new GameObject(name + " (placeholder)");
            Transform t = root.transform;
            void Child(string n, Vector3 size, Vector3 c, string mat) => Box(n, size, c, mat).transform.SetParent(t, false);

            if (name.StartsWith("bldg_"))
            {
                float h = name.Contains("tower") ? 18f : name.Contains("hangar") ? 9f : 8f;
                Child("Body", new Vector3(11f, h, 11f), new Vector3(0, h / 2f, 0), "SKY_Sandstone");
                Child("Roof", new Vector3(11.4f, 0.5f, 11.4f), new Vector3(0, h + 0.25f, 0), "SKY_Pearl");
            }
            else if (name.StartsWith("palm"))
            {
                Child("Trunk", new Vector3(0.45f, 6f, 0.45f), new Vector3(0, 3f, 0), "SKY_PalmTrunk");
                Child("Crown", new Vector3(4f, 1.2f, 4f), new Vector3(0, 6.2f, 0), "SKY_PalmLeaf");
            }
            else if (name.StartsWith("foldstation"))
            {
                Child("Base", new Vector3(1.6f, 0.4f, 1.6f), new Vector3(0, 0.2f, 0), "SKY_Pearl");
                Child("Column", new Vector3(0.9f, 2.4f, 0.9f), new Vector3(0, 1.6f, 0), "SKY_Pearl");
                Child("LensRing", new Vector3(1.4f, 1.4f, 0.15f), new Vector3(0, 2.4f, 0.5f), "SKY_TealGlow");
            }
            else if (name == "atelier_platform")
            {
                var c = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Object.DestroyImmediate(c.GetComponent<Collider>());
                c.name = "Terrace";
                c.transform.SetParent(t, false);
                c.transform.localScale = new Vector3(14f, 0.3f, 14f);
                c.transform.localPosition = new Vector3(0f, -0.3f, 0f);
                SetMaterial(c, "SKY_Pearl");
                WhiteColors(c);
            }
            else if (name == "plinth")
            {
                Child("Top", new Vector3(1.6f, 0.08f, 1.2f), new Vector3(0, 0.86f, 0), "SKY_Pearl");
                Child("Base", new Vector3(1.3f, 0.82f, 0.9f), new Vector3(0, 0.41f, 0), "SKY_SandstoneDeep");
                Child("PlinthRim", new Vector3(1.64f, 0.03f, 1.24f), new Vector3(0, 0.83f, 0), "SKY_TealGlow");
            }
            else if (name == "plinth_tray") Child("Tray", new Vector3(1.1f, 0.04f, 0.18f), new Vector3(0, 0.02f, 0), "SKY_Brass");
            else if (name == "cell_dock") Child("Dock", new Vector3(0.45f, 0.6f, 0.45f), new Vector3(0, 0.3f, 0), "SKY_Teal");
            else if (name == "switch_box")
            {
                Child("Box", new Vector3(0.5f, 1.1f, 0.4f), new Vector3(0, 0.55f, 0), "SKY_Pearl");
                var lever = Box("Lever", new Vector3(0.08f, 0.45f, 0.08f), new Vector3(0, 0.22f, 0), "SKY_Coral");
                var pivot = new GameObject("LeverPivot").transform;
                pivot.SetParent(t, false);
                pivot.localPosition = new Vector3(0, 1.1f, 0f);
                lever.transform.SetParent(pivot, false);
            }
            else if (name == "runway_beacon")
            {
                Child("Post", new Vector3(0.18f, 0.35f, 0.18f), new Vector3(0, 0.17f, 0), "SKY_Ink");
                Child("Lens", new Vector3(0.24f, 0.14f, 0.24f), new Vector3(0, 0.41f, 0), "SKY_Light");
            }
            else if (name == "courier_car")
            {
                Child("Body", new Vector3(1.6f, 1.0f, 3.2f), new Vector3(0, 0.9f, 0), "SKY_Pearl");
                Child("Canopy", new Vector3(1.5f, 0.1f, 1.6f), new Vector3(0, 1.6f, -0.2f), "SKY_Teal");
                foreach (var (n, p) in new[] { ("Wheel_FL", new Vector3(-0.72f, 0.32f, 1.08f)), ("Wheel_FR", new Vector3(0.72f, 0.32f, 1.08f)), ("Wheel_RL", new Vector3(-0.72f, 0.32f, -1.02f)), ("Wheel_RR", new Vector3(0.72f, 0.32f, -1.02f)) })
                    Child(n, new Vector3(0.24f, 0.64f, 0.64f), p, "SKY_Rubber");
            }
            else if (name == "convoy_shuttle") Child("Body", new Vector3(2f, 2.4f, 5.2f), new Vector3(0, 1.4f, 0), "SKY_Pearl");
            else if (name.StartsWith("city_car")) Child("Body", new Vector3(1.7f, 1.4f, 3.8f), new Vector3(0, 0.85f, 0), name.EndsWith("a") ? "SKY_Sandstone" : "SKY_Teal");
            else if (name == "aircraft")
            {
                Child("Fuselage", new Vector3(1.8f, 1.9f, 13f), new Vector3(0, 2.2f, 0), "SKY_Pearl");
                Child("Wing", new Vector3(16f, 0.25f, 2.2f), new Vector3(0, 3.1f, 0.5f), "SKY_Pearl");
                Child("Tail", new Vector3(0.2f, 2.4f, 1.6f), new Vector3(0, 3.8f, -5.8f), "SKY_Teal");
            }
            else if (name.StartsWith("passenger")) Child("Body", new Vector3(0.45f, 1.7f, 0.3f), new Vector3(0, 0.85f, 0), "SKY_Teal");
            else if (name.StartsWith("cloud") || name.StartsWith("storm_cloud")) Child("Puff", new Vector3(30f, 8f, 18f), Vector3.zero, name.StartsWith("storm") ? "SKY_Ink" : "SKY_Pearl");
            else if (name.StartsWith("barrier")) Child("Barrier", new Vector3(3f, 0.9f, 0.3f), new Vector3(0, 0.45f, 0), "SKY_Coral");
            else if (name == "street_lamp")
            {
                Child("Post", new Vector3(0.16f, 4.8f, 0.16f), new Vector3(0, 2.4f, 0), "SKY_Brass");
                Child("Lamp", new Vector3(0.4f, 0.5f, 0.4f), new Vector3(0, 4.9f, 0), "SKY_Light");
            }
            else Child("Block", new Vector3(1f, 1f, 1f), new Vector3(0, 0.5f, 0), "SKY_Pearl");
            return root;
        }
    }

    /// <summary>Stores generated meshes as assets so scenes reference them persistently.</summary>
    public static class PlaceholderMeshes
    {
        public const string Folder = "Assets/Skyfold/Art/Generated";

        public static Mesh Store(string key, Mesh mesh)
        {
            System.IO.Directory.CreateDirectory(Folder);
            string path = Folder + "/" + key + ".asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null) { Object.DestroyImmediate(mesh); return existing; }
            AssetDatabase.CreateAsset(mesh, path);
            return mesh;
        }
    }
}
