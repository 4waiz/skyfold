using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Hands the project's two font families to the UI kit before any screen is built.</summary>
    [DefaultExecutionOrder(-1000)]
    public sealed class UITheme : MonoBehaviour
    {
        public TMP_FontAsset heading;
        public TMP_FontAsset body;
        public Sprite noorPortrait;

        void Awake()
        {
            if (heading != null) UIStyle.HeadingFont = heading;
            if (body != null) UIStyle.BodyFont = body;
        }
    }
}
