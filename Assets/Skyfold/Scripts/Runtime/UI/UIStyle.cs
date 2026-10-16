using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Palette, type and spacing for every screen (desktop and VR share it).</summary>
    public static class UIStyle
    {
        public static readonly Color Pearl = Hex("#F4EFE6");
        public static readonly Color PearlDeep = Hex("#E8DFCF");
        public static readonly Color Sand = Hex("#D9B98C");
        public static readonly Color Teal = Hex("#0F6F73");
        public static readonly Color TealLight = Hex("#3FA7A3");
        public static readonly Color TealGlow = Hex("#35E0D0");
        public static readonly Color Coral = Hex("#F2714B");
        public static readonly Color Gold = Hex("#D9A441");
        public static readonly Color Ink = Hex("#22333B");
        public static readonly Color InkSoft = Hex("#4A5A61");
        public static readonly Color Shadow = new Color(0.05f, 0.1f, 0.12f, 0.28f);
        public static readonly Color PanelGlass = new Color(0.96f, 0.94f, 0.9f, 0.96f);
        public static readonly Color Scrim = new Color(0.07f, 0.12f, 0.14f, 0.45f);

        public static TMP_FontAsset HeadingFont;
        public static TMP_FontAsset BodyFont;

        // Desktop sizes are in reference pixels (1920x1080); VR canvases use 1 unit = 1 mm.
        public const float TitleSize = 96f;
        public const float HeadingSize = 44f;
        public const float BodySize = 28f;
        public const float SmallSize = 22f;
        public const float ButtonHeight = 64f;
        public const float Gap = 14f;
        public const float Radius = 18f;

        public static Color Hex(string hex) => ColorUtility.TryParseHtmlString(hex, out var c) ? c : Color.magenta;

        public static string MedalColor(string medal) =>
            medal == "Gold" ? "#D9A441" : medal == "Silver" ? "#9AA7AD" : medal == "Bronze" ? "#B9784A" : "#4A5A61";
    }
}
