using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>Uses the generated SKYFOLD emblem as the application (.exe) icon.</summary>
    public static class IconSetup
    {
        public const string IconPath = "Assets/Skyfold/Art/Icons/skyfold_icon.png";

        [MenuItem("SKYFOLD/Setup/Apply App Icon")]
        public static void Apply()
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(IconPath);
            if (tex == null) { Debug.LogWarning("[SKYFOLD] Icon missing: " + IconPath + " (run tools/icons/make_icons.py)"); return; }
            var imp = (TextureImporter)AssetImporter.GetAtPath(IconPath);
            if (imp != null && (imp.textureCompression != TextureImporterCompression.Uncompressed || imp.mipmapEnabled))
            {
                imp.textureCompression = TextureImporterCompression.Uncompressed;
                imp.mipmapEnabled = false;
                imp.alphaIsTransparency = true;
                imp.SaveAndReimport();
                tex = AssetDatabase.LoadAssetAtPath<Texture2D>(IconPath);
            }
            PlayerSettings.SetIcons(NamedBuildTarget.Unknown, new[] { tex }, IconKind.Any);
            var sizes = PlayerSettings.GetIconSizes(NamedBuildTarget.Standalone, IconKind.Application);
            PlayerSettings.SetIcons(NamedBuildTarget.Standalone, sizes.Select(_ => tex).ToArray(), IconKind.Application);
            Debug.Log("[SKYFOLD] Application icon set.");
        }
    }
}
