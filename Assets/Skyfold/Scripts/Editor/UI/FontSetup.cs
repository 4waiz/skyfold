using System.IO;
using System.Linq;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Imports the two OFL font families into TextMeshPro (dynamic SDF assets pre-filled with Latin
    /// glyphs) and checks every shipped UI/caption string for missing glyphs.
    /// </summary>
    public static class FontSetup
    {
        public const string SourceDir = "source-art/fonts_src";
        public const string Folder = "Assets/Skyfold/Fonts";
        public const string HeadingAsset = Folder + "/Heading SDF.asset";
        public const string BodyAsset = Folder + "/Body SDF.asset";
        const string Essentials = "Packages/com.unity.ugui/Package Resources/TMP Essential Resources.unitypackage";

        static readonly string Prefill =
            " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~" +
            " °·×é‘’“”–—…";

        [MenuItem("SKYFOLD/Setup/Fonts")]
        public static void Build()
        {
            EnsureEssentials();
            Directory.CreateDirectory(Folder);
            // Ship only the faces in use (the variable source font stays in source-art).
            foreach (var name in new[] { "Unbounded-SemiBold.ttf", "Unbounded-OFL.txt", "AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf", "AtkinsonHyperlegible-OFL.txt" })
            {
                string f = Path.Combine(SourceDir, name);
                if (File.Exists(f)) File.Copy(f, Path.Combine(Folder, name), true);
                else Debug.LogWarning("[SKYFOLD] Font source missing: " + f);
            }
            AssetDatabase.Refresh();

            string headingTtf = File.Exists(Folder + "/Unbounded-SemiBold.ttf") ? Folder + "/Unbounded-SemiBold.ttf" : Folder + "/Unbounded[wght].ttf";
            var heading = Make(headingTtf, HeadingAsset);
            var body = Make(Folder + "/AtkinsonHyperlegible-Regular.ttf", BodyAsset);
            var bold = AssetDatabase.LoadAssetAtPath<Font>(Folder + "/AtkinsonHyperlegible-Bold.ttf");
            if (body != null && bold != null)
            {
                // Real bold weight for <b> text instead of faux bold.
                var boldAsset = Make(Folder + "/AtkinsonHyperlegible-Bold.ttf", Folder + "/Body Bold SDF.asset");
                if (boldAsset != null)
                {
                    var table = body.fontWeightTable;
                    table[7].regularTypeface = boldAsset;
                    EditorUtility.SetDirty(body);
                }
            }
            AssetDatabase.SaveAssets();
            CheckCoverage(heading, body);
        }

        static void EnsureEssentials()
        {
            if (AssetDatabase.FindAssets("t:TMP_Settings").Length == 0)
            {
                if (File.Exists(Path.GetFullPath(Essentials)))
                {
                    AssetDatabase.ImportPackage(Essentials, false);
                    AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                    Debug.Log("[SKYFOLD] Imported TMP Essential Resources.");
                }
                else Debug.LogWarning("[SKYFOLD] TMP Essential Resources package not found at " + Essentials);
            }
            // In the same batch run the settings singleton may not be loadable yet; hand it over directly.
            var field = typeof(TMP_Settings).GetField("s_Instance", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);
            if (field != null && field.GetValue(null) == null)
            {
                var guid = AssetDatabase.FindAssets("t:TMP_Settings").FirstOrDefault();
                var settings = guid != null ? AssetDatabase.LoadAssetAtPath<TMP_Settings>(AssetDatabase.GUIDToAssetPath(guid)) : null;
                if (settings != null) field.SetValue(null, settings);
            }
        }

        static TMP_FontAsset Make(string ttfPath, string assetPath)
        {
            var font = AssetDatabase.LoadAssetAtPath<Font>(ttfPath);
            if (font == null) { Debug.LogError("[SKYFOLD] Font missing: " + ttfPath); return null; }
            var fa = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(assetPath);
            if (fa == null)
            {
                fa = TMP_FontAsset.CreateFontAsset(font, 90, 9, GlyphRenderMode.SDFAA, 2048, 2048, AtlasPopulationMode.Dynamic, false);
                fa.name = Path.GetFileNameWithoutExtension(assetPath);
                AssetDatabase.CreateAsset(fa, assetPath);
                fa.material.name = fa.name + " Material";
                AssetDatabase.AddObjectToAsset(fa.material, fa);
                foreach (var tex in fa.atlasTextures)
                {
                    tex.name = fa.name + " Atlas";
                    AssetDatabase.AddObjectToAsset(tex, fa);
                }
            }
            // Bake every glyph the game uses, then freeze the atlas (no runtime glyph generation).
            fa.atlasPopulationMode = AtlasPopulationMode.Dynamic;
            fa.TryAddCharacters(Prefill + UsedCharacters(), out string missing);
            if (!string.IsNullOrEmpty(missing)) Debug.LogWarning($"[SKYFOLD] {fa.name}: font file lacks {missing.Length} glyph(s): \"{missing}\"");
            fa.atlasPopulationMode = AtlasPopulationMode.Static;
            EditorUtility.SetDirty(fa);
            AssetDatabase.SaveAssets();
            return fa;
        }

        /// <summary>Every character in captions, credits and runtime C# string literals.</summary>
        public static string UsedCharacters()
        {
            var text = new StringBuilder();
            var vo = AssetDatabase.LoadAssetAtPath<TextAsset>("Assets/Skyfold/Resources/Dialogue/vo_lines.json");
            if (vo != null) text.Append(vo.text);
            text.Append(CreditsText.Body).Append(SkyfoldInfo.ProjectLabel).Append(SkyfoldInfo.Credit);
            foreach (var cs in Directory.GetFiles("Assets/Skyfold/Scripts/Runtime", "*.cs", SearchOption.AllDirectories))
                foreach (System.Text.RegularExpressions.Match m in System.Text.RegularExpressions.Regex.Matches(File.ReadAllText(cs), "\"([^\"\\\\]|\\\\.)*\""))
                    text.Append(m.Value);
            return new string(text.ToString().Where(c => c >= 32 && c != '\\').Distinct().ToArray());
        }
        /// <summary>Checks that every used character is in the baked atlases (no missing-glyph boxes).</summary>
        public static int CheckCoverage(TMP_FontAsset heading, TMP_FontAsset body)
        {
            string chars = UsedCharacters();
            int missingCount = 0;
            foreach (var fa in new[] { body, heading })
            {
                if (fa == null) continue;
                fa.HasCharacters(chars, out System.Collections.Generic.List<char> missing);
                if (missing != null && missing.Count > 0)
                {
                    missingCount += missing.Count;
                    Debug.LogWarning($"[SKYFOLD] Font {fa.name} is missing glyphs: \"{new string(missing.ToArray())}\" ({string.Join(" ", missing.Select(c => "U+" + ((int)c).ToString("X4")))})");
                }
                else Debug.Log($"[SKYFOLD] Font {fa.name}: all {chars.Length} UI characters present.");
            }
            return missingCount;
        }
    }
}