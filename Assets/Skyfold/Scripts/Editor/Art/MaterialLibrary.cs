using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Skyfold.EditorTools
{
    /// <summary>Creates the shared palette materials (SKY_*) and the special effect materials.</summary>
    public static class MaterialLibrary
    {
        public const string Folder = "Assets/Skyfold/Art/Materials";
        public const string TexFolder = "Assets/Skyfold/Art/Textures";

        struct Entry
        {
            public string Name, Hex;
            public float Smooth, Emission, Alpha;
            public Entry(string n, string h, float s, float e = 0f, float a = 1f) { Name = n; Hex = h; Smooth = s; Emission = e; Alpha = a; }
        }

        static readonly Entry[] Palette =
        {
            new Entry("SKY_Pearl", "#F4EFE6", 0.3f),
            new Entry("SKY_Ivory", "#EFE6D2", 0.45f),
            new Entry("SKY_Sandstone", "#D9B98C", 0.12f),
            new Entry("SKY_SandstoneDeep", "#C49A6C", 0.1f),
            new Entry("SKY_Terracotta", "#C8754F", 0.15f),
            new Entry("SKY_Teal", "#0F6F73", 0.45f),
            new Entry("SKY_TealLight", "#3FA7A3", 0.55f),
            new Entry("SKY_TealGlow", "#35E0D0", 0.6f, 2.4f),
            new Entry("SKY_Coral", "#F2714B", 0.3f),
            new Entry("SKY_Gold", "#D9A441", 0.6f),
            new Entry("SKY_Brass", "#B8893B", 0.7f),
            new Entry("SKY_Ink", "#22333B", 0.35f),
            new Entry("SKY_Glass", "#6FB7C4", 0.9f, 0f, 0.42f),
            new Entry("SKY_Road", "#3E4A52", 0.12f),
            new Entry("SKY_RoadLine", "#F4EFE6", 0.2f),
            new Entry("SKY_Kerb", "#CDBFA9", 0.15f),
            new Entry("SKY_Wood", "#9A6B45", 0.2f),
            new Entry("SKY_PalmTrunk", "#8B6B4A", 0.1f),
            new Entry("SKY_PalmLeaf", "#5E8C4A", 0.25f),
            new Entry("SKY_Flower", "#E0557A", 0.25f),
            new Entry("SKY_Fabric", "#F7F1E6", 0.1f),
            new Entry("SKY_Metal", "#AEB6BA", 0.6f),
            new Entry("SKY_Rubber", "#2B2F33", 0.15f),
            new Entry("SKY_Light", "#FFD9A0", 0.3f, 1.8f),
        };

        public static IEnumerable<string> PaletteNames
        {
            get { foreach (var e in Palette) yield return e.Name; }
        }

        static Shader Lit => Shader.Find("Skyfold/StylizedLit");
        static Shader Unlit => Shader.Find("Skyfold/Unlit");

        public static Material Get(string name)
        {
            var path = Folder + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                BuildAll();
                m = AssetDatabase.LoadAssetAtPath<Material>(path);
            }
            return m;
        }

        public static Material TryGet(string name) => AssetDatabase.LoadAssetAtPath<Material>(Folder + "/" + name + ".mat");

        static Material Ensure(string name, Shader shader)
        {
            Directory.CreateDirectory(Folder);
            var path = Folder + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(m, path);
            }
            else if (m.shader != shader) m.shader = shader;
            return m;
        }

        public static void BuildAll()
        {
            if (Lit == null || Unlit == null)
            {
                Debug.LogError("[SKYFOLD] Skyfold shaders are not compiled yet.");
                return;
            }
            foreach (var e in Palette)
            {
                var m = Ensure(e.Name, Lit);
                var c = UIStyle.Hex(e.Hex);
                c.a = e.Alpha;
                m.SetColor("_BaseColor", c);
                m.SetFloat("_Smoothness", e.Smooth);
                m.SetColor("_EmissionColor", e.Emission > 0f ? c * e.Emission : Color.black);
                m.SetFloat("_AOStrength", e.Emission > 0f ? 0.2f : 0.85f);
                SetTransparent(m, e.Alpha < 1f);
                m.enableInstancing = true;
                EditorUtility.SetDirty(m);
            }

            // Special materials.
            var water = Ensure("SKY_Water", Shader.Find("Skyfold/Water"));
            water.SetColor("_DeepColor", new Color(0.03f, 0.3f, 0.34f));
            water.SetColor("_ShallowColor", new Color(0.12f, 0.55f, 0.55f));
            EditorUtility.SetDirty(water);

            var miniWater = Ensure("SKY_WaterMini", Shader.Find("Skyfold/Water"));
            miniWater.SetColor("_DeepColor", new Color(0.05f, 0.36f, 0.4f));
            miniWater.SetColor("_ShallowColor", new Color(0.16f, 0.6f, 0.6f));
            miniWater.SetFloat("_WaveHeight", 0f);
            miniWater.SetFloat("_RippleScale", 55f);
            miniWater.SetFloat("_RippleStrength", 0.25f);
            EditorUtility.SetDirty(miniWater);

            var sky = Ensure("SKY_Sky", Shader.Find("Skyfold/Sky"));
            EditorUtility.SetDirty(sky);

            var ghost = Ensure("SKY_Ghost", Unlit);
            ghost.SetColor("_BaseColor", new Color(0.21f, 0.88f, 0.82f, 0.45f));
            SetUnlitBlend(ghost, true, false);

            var ring = Ensure("SKY_Ring", Unlit);
            ring.SetColor("_BaseColor", new Color(0.21f, 0.88f, 0.82f, 1f));
            ring.SetColor("_EmissionColor", new Color(0.21f, 0.88f, 0.82f) * 1.5f);
            SetUnlitBlend(ring, false, false);

            var guide = Ensure("SKY_Guide", Unlit);
            guide.SetColor("_BaseColor", new Color(0.85f, 0.64f, 0.25f, 0.85f));
            guide.SetColor("_EmissionColor", new Color(0.85f, 0.64f, 0.25f) * 1.2f);
            SetUnlitBlend(guide, true, false);
            guide.SetFloat("_Cull", 0f);

            var line = Ensure("SKY_MiniLine", Unlit);
            line.SetTexture("_BaseMap", DashTexture());
            line.SetColor("_BaseColor", new Color(1f, 0.82f, 0.4f, 1f));
            line.SetColor("_EmissionColor", new Color(0.85f, 0.64f, 0.25f) * 1.6f);
            SetUnlitBlend(line, true, false);

            var check = Ensure("SKY_IconCheck", Unlit);
            check.SetTexture("_BaseMap", IconTexture("icon_check", true));
            check.SetColor("_BaseColor", new Color(0.21f, 0.88f, 0.82f, 1f));
            check.SetColor("_EmissionColor", new Color(0.21f, 0.88f, 0.82f) * 1.2f);
            SetUnlitBlend(check, true, true);
            check.SetFloat("_Cull", 0f);

            var cross = Ensure("SKY_IconCross", Unlit);
            cross.SetTexture("_BaseMap", IconTexture("icon_cross", false));
            cross.SetColor("_BaseColor", new Color(0.95f, 0.44f, 0.29f, 1f));
            cross.SetColor("_EmissionColor", new Color(0.95f, 0.44f, 0.29f) * 1.2f);
            SetUnlitBlend(cross, true, true);
            cross.SetFloat("_Cull", 0f);

            var marker = Ensure("SKY_Marker", Unlit);
            marker.SetColor("_BaseColor", new Color(0.21f, 0.88f, 0.82f, 0.85f));
            marker.SetColor("_EmissionColor", new Color(0.21f, 0.88f, 0.82f) * 1.4f);
            SetUnlitBlend(marker, true, false);
            marker.SetFloat("_Cull", 0f);

            var rain = Ensure("SKY_Rain", Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Unlit);
            rain.SetColor("_BaseColor", new Color(0.8f, 0.85f, 0.95f, 0.35f));
            EditorUtility.SetDirty(rain);

            var invisible = Ensure("SKY_Seabed", Lit);
            invisible.SetColor("_BaseColor", new Color(0.05f, 0.22f, 0.26f));
            invisible.SetFloat("_Smoothness", 0.1f);

            AssetDatabase.SaveAssets();
        }

        public static void SetTransparent(Material m, bool transparent)
        {
            if (transparent)
            {
                m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
                m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
                m.SetFloat("_ZWrite", 0f);
                m.renderQueue = (int)RenderQueue.Transparent;
                m.SetOverrideTag("RenderType", "Transparent");
            }
            else
            {
                m.SetFloat("_SrcBlend", (float)BlendMode.One);
                m.SetFloat("_DstBlend", (float)BlendMode.Zero);
                m.SetFloat("_ZWrite", 1f);
                m.renderQueue = -1;
                m.SetOverrideTag("RenderType", "Opaque");
            }
        }

        static void SetUnlitBlend(Material m, bool transparent, bool overlay)
        {
            SetTransparent(m, transparent);
            if (overlay) { m.SetFloat("_ZTest", (float)CompareFunction.Always); m.renderQueue = (int)RenderQueue.Overlay; }
            else m.SetFloat("_ZTest", (float)CompareFunction.LessEqual);
            EditorUtility.SetDirty(m);
        }

        // ------------------------------------------------------------------ generated textures
        static Texture2D SaveTexture(string name, Texture2D tex)
        {
            Directory.CreateDirectory(TexFolder);
            string path = TexFolder + "/" + name + ".png";
            File.WriteAllBytes(path, tex.EncodeToPNG());
            AssetDatabase.ImportAsset(path);
            var imp = (TextureImporter)AssetImporter.GetAtPath(path);
            imp.alphaIsTransparency = true;
            imp.mipmapEnabled = true;
            imp.wrapMode = name.StartsWith("dash") ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
            imp.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static float Seg(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 ab = b - a;
            float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
            return Vector2.Distance(p, a + ab * t);
        }

        static Texture2D IconTexture(string name, bool check)
        {
            var existing = AssetDatabase.LoadAssetAtPath<Texture2D>(TexFolder + "/" + name + ".png");
            if (existing != null) return existing;
            const int size = 128;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x + 0.5f, y + 0.5f) / size;
                    float ringD = Mathf.Abs(Vector2.Distance(p, new Vector2(0.5f, 0.5f)) - 0.42f);
                    float d = check
                        ? Mathf.Min(Seg(p, new Vector2(0.27f, 0.52f), new Vector2(0.44f, 0.33f)), Seg(p, new Vector2(0.44f, 0.33f), new Vector2(0.74f, 0.68f)))
                        : Mathf.Min(Seg(p, new Vector2(0.32f, 0.32f), new Vector2(0.68f, 0.68f)), Seg(p, new Vector2(0.32f, 0.68f), new Vector2(0.68f, 0.32f)));
                    float a = Mathf.Max(Mathf.Clamp01((0.06f - d) * size + 0.5f), Mathf.Clamp01((0.035f - ringD) * size + 0.5f));
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            return SaveTexture(name, tex);
        }

        static Texture2D DashTexture()
        {
            var existing = AssetDatabase.LoadAssetAtPath<Texture2D>(TexFolder + "/dash.png");
            if (existing != null) return existing;
            var tex = new Texture2D(64, 8, TextureFormat.RGBA32, false);
            for (int y = 0; y < 8; y++)
                for (int x = 0; x < 64; x++)
                {
                    float a = x < 40 ? Mathf.Clamp01(Mathf.Min(x, 40 - x) / 6f) : 0.15f;
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            return SaveTexture("dash", tex);
        }
    }
}
