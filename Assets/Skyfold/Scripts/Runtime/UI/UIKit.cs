using System;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>Builds the game's uGUI/TextMeshPro widgets in code with one consistent style.</summary>
    public static class UIKit
    {
        static Sprite s_Rounded, s_Circle, s_Check, s_Cross, s_Arrow, s_Ring;

        public static Sprite Rounded => s_Rounded != null ? s_Rounded : (s_Rounded = MakeRounded(96, 30));
        public static Sprite Circle => s_Circle != null ? s_Circle : (s_Circle = MakeCircle(128, false));
        public static Sprite Ring => s_Ring != null ? s_Ring : (s_Ring = MakeCircle(128, true));
        public static Sprite Check => s_Check != null ? s_Check : (s_Check = MakeIcon(128, true));
        public static Sprite Cross => s_Cross != null ? s_Cross : (s_Cross = MakeIcon(128, false));
        public static Sprite Arrow => s_Arrow != null ? s_Arrow : (s_Arrow = MakeArrow(128));

        // ------------------------------------------------------------------ procedural sprites
        static Sprite MakeRounded(int size, int radius)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, name = "UI Rounded" };
            var px = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float dx = Mathf.Max(0f, Mathf.Max(radius - x - 0.5f, x + 0.5f - (size - radius)));
                    float dy = Mathf.Max(0f, Mathf.Max(radius - y - 0.5f, y + 0.5f - (size - radius)));
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(radius - d + 0.5f);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
        }

        static Sprite MakeCircle(int size, bool ring)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = ring ? "UI Ring" : "UI Circle" };
            var px = new Color32[size * size];
            float r = size * 0.5f - 1f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(size * 0.5f, size * 0.5f));
                    float a = Mathf.Clamp01(r - d + 0.5f);
                    if (ring) a *= Mathf.Clamp01(d - (r - size * 0.11f) + 0.5f);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        static float SegmentDistance(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 ab = b - a;
            float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
            return Vector2.Distance(p, a + ab * t);
        }

        static Sprite MakeIcon(int size, bool check)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = check ? "UI Check" : "UI Cross" };
            var px = new Color32[size * size];
            float w = size * 0.075f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x + 0.5f, y + 0.5f) / size;
                    float d;
                    if (check) d = Mathf.Min(SegmentDistance(p, new Vector2(0.2f, 0.52f), new Vector2(0.42f, 0.28f)), SegmentDistance(p, new Vector2(0.42f, 0.28f), new Vector2(0.82f, 0.74f)));
                    else d = Mathf.Min(SegmentDistance(p, new Vector2(0.25f, 0.25f), new Vector2(0.75f, 0.75f)), SegmentDistance(p, new Vector2(0.25f, 0.75f), new Vector2(0.75f, 0.25f)));
                    float a = Mathf.Clamp01((w / size - d) * size + 0.5f);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        static Sprite MakeArrow(int size)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "UI Arrow" };
            var px = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x + 0.5f, y + 0.5f) / size;
                    float d = Mathf.Min(SegmentDistance(p, new Vector2(0.25f, 0.2f), new Vector2(0.75f, 0.5f)), SegmentDistance(p, new Vector2(0.75f, 0.5f), new Vector2(0.25f, 0.8f)));
                    float a = Mathf.Clamp01((0.09f - d) * size + 0.5f);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        // ------------------------------------------------------------------ canvases
        public static Canvas ScreenCanvas(string name, int order, Transform parent = null)
        {
            var go = new GameObject(name, typeof(RectTransform));
            if (parent != null) go.transform.SetParent(parent, false);
            var c = go.AddComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            c.sortingOrder = order;
            var s = go.AddComponent<CanvasScaler>();
            s.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            s.referenceResolution = new Vector2(1920, 1080);
            s.matchWidthOrHeight = 0.5f;
            go.AddComponent<GraphicRaycaster>();
            return c;
        }

        public static RectTransform Rect(Transform parent, string name)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            go.layer = parent != null ? parent.gameObject.layer : 0;
            return (RectTransform)go.transform;
        }

        public static void Stretch(RectTransform rt, float inset = 0f)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(inset, inset);
            rt.offsetMax = new Vector2(-inset, -inset);
        }

        public static Image Image(Transform parent, string name, Color color, Sprite sprite = null, bool sliced = true)
        {
            var rt = Rect(parent, name);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite != null ? sprite : Rounded;
            img.type = sliced && img.sprite == Rounded ? UnityEngine.UI.Image.Type.Sliced : UnityEngine.UI.Image.Type.Simple;
            img.pixelsPerUnitMultiplier = 1f;
            img.color = color;
            img.raycastTarget = false;
            return img;
        }

        public static RectTransform Panel(Transform parent, string name, Color color, float padding = 32f, float spacing = UIStyle.Gap, bool shadow = true)
        {
            var root = Rect(parent, name);
            if (shadow)
            {
                var sh = Image(root, "Shadow", UIStyle.Shadow);
                Stretch(sh.rectTransform, -10f);
                sh.rectTransform.anchoredPosition = new Vector2(0f, -8f);
                sh.gameObject.AddComponent<LayoutElement>().ignoreLayout = true;
            }
            var bg = root.gameObject.AddComponent<Image>();
            bg.sprite = Rounded;
            bg.type = UnityEngine.UI.Image.Type.Sliced;
            bg.color = color;
            var v = root.gameObject.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset((int)padding, (int)padding, (int)padding, (int)padding);
            v.spacing = spacing;
            v.childControlWidth = true;
            v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;
            var fit = root.gameObject.AddComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            return root;
        }

        public static TextMeshProUGUI Text(Transform parent, string text, float size, Color color, bool heading = false, TextAlignmentOptions align = TextAlignmentOptions.Left, string name = "Text")
        {
            var rt = Rect(parent, name);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            var font = heading ? UIStyle.HeadingFont : UIStyle.BodyFont;
            if (font != null) t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.textWrappingMode = TextWrappingModes.Normal;
            t.raycastTarget = false;
            t.lineSpacing = heading ? -6f : 4f;
            return t;
        }

        public static LayoutElement Layout(Component c, float preferredHeight = -1f, float minHeight = -1f, float flexibleWidth = -1f, float preferredWidth = -1f)
        {
            if (!c.TryGetComponent(out LayoutElement le)) le = c.gameObject.AddComponent<LayoutElement>();
            if (preferredHeight >= 0f) le.preferredHeight = preferredHeight;
            if (minHeight >= 0f) le.minHeight = minHeight;
            if (flexibleWidth >= 0f) le.flexibleWidth = flexibleWidth;
            if (preferredWidth >= 0f) le.preferredWidth = preferredWidth;
            return le;
        }

        public static Button Button(Transform parent, string label, Action onClick, bool primary = false, float height = UIStyle.ButtonHeight, string detail = null)
        {
            var rt = Rect(parent, "Button " + label);
            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = Rounded;
            bg.type = UnityEngine.UI.Image.Type.Sliced;
            bg.color = primary ? UIStyle.Teal : UIStyle.PearlDeep;
            var b = rt.gameObject.AddComponent<Button>();
            b.transition = Selectable.Transition.None;
            b.targetGraphic = bg;
            b.onClick.AddListener(() => { AudioDirector.Instance?.PlayUI("ui_click"); onClick?.Invoke(); });
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(28, 28, 8, 8);
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = true;
            var t = Text(rt, label, UIStyle.BodySize, primary ? UIStyle.Pearl : UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            t.fontStyle = FontStyles.Bold;
            TextMeshProUGUI d = null;
            if (!string.IsNullOrEmpty(detail))
            {
                d = Text(rt, detail, UIStyle.SmallSize, primary ? UIStyle.Pearl : UIStyle.InkSoft, false, TextAlignmentOptions.Right, "Detail");
                Layout(d, -1f, -1f, 0f, 260f);
            }
            Layout(b, height, height);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, d, primary);
            return b;
        }

        public static Toggle Toggle(Transform parent, string label, bool value, Action<bool> onChange)
        {
            var rt = Rect(parent, "Toggle " + label);
            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = Rounded;
            bg.type = UnityEngine.UI.Image.Type.Sliced;
            bg.color = UIStyle.PearlDeep;
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(28, 22, 8, 8);
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            var t = Text(rt, label, UIStyle.BodySize, UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            Layout(t, -1f, -1f, 1f);
            var box = Image(rt, "Box", UIStyle.Pearl, Rounded);
            Layout(box, 40f, 40f, 0f, 76f);
            var knob = Image(box.transform, "Knob", UIStyle.InkSoft, Circle, false);
            knob.rectTransform.sizeDelta = new Vector2(30f, 30f);
            var state = Text(rt, value ? "On" : "Off", UIStyle.SmallSize, UIStyle.InkSoft, false, TextAlignmentOptions.Right, "State");
            Layout(state, -1f, -1f, 0f, 60f);

            var tg = rt.gameObject.AddComponent<Toggle>();
            tg.transition = Selectable.Transition.None;
            tg.targetGraphic = bg;
            tg.isOn = value;
            void Refresh(bool on)
            {
                knob.rectTransform.anchoredPosition = new Vector2(on ? 18f : -18f, 0f);
                knob.color = on ? UIStyle.Teal : UIStyle.InkSoft;
                box.color = on ? new Color(0.21f, 0.88f, 0.82f, 0.35f) : UIStyle.Pearl;
                state.text = on ? "On" : "Off";
            }
            Refresh(value);
            tg.onValueChanged.AddListener(v => { Refresh(v); AudioDirector.Instance?.PlayUI("ui_toggle"); onChange?.Invoke(v); });
            Layout(tg, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, null, false);
            return tg;
        }

        public static Slider Slider(Transform parent, string label, float value, Action<float> onChange, float min = 0f, float max = 1f, Func<float, string> format = null, bool whole = false)
        {
            format ??= v => Mathf.RoundToInt(Mathf.InverseLerp(min, max, v) * 100f) + "%";
            var rt = Rect(parent, "Slider " + label);
            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = Rounded;
            bg.type = UnityEngine.UI.Image.Type.Sliced;
            bg.color = UIStyle.PearlDeep;
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(28, 22, 8, 8);
            h.spacing = 18;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            var t = Text(rt, label, UIStyle.BodySize, UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            Layout(t, -1f, -1f, 1f);

            var track = Rect(rt, "Track");
            Layout(track, 40f, 40f, 0f, 260f);
            var trackBg = Image(track, "Bg", UIStyle.Pearl);
            trackBg.rectTransform.anchorMin = new Vector2(0f, 0.35f);
            trackBg.rectTransform.anchorMax = new Vector2(1f, 0.65f);
            trackBg.rectTransform.offsetMin = trackBg.rectTransform.offsetMax = Vector2.zero;
            var fillArea = Rect(track, "Fill Area");
            fillArea.anchorMin = new Vector2(0f, 0.35f);
            fillArea.anchorMax = new Vector2(1f, 0.65f);
            fillArea.offsetMin = fillArea.offsetMax = Vector2.zero;
            var fill = Image(fillArea, "Fill", UIStyle.Teal);
            fill.rectTransform.anchorMin = Vector2.zero;
            fill.rectTransform.anchorMax = new Vector2(0f, 1f);
            fill.rectTransform.offsetMin = fill.rectTransform.offsetMax = Vector2.zero;
            var handleArea = Rect(track, "Handle Area");
            Stretch(handleArea);
            var handle = Image(handleArea, "Handle", UIStyle.Teal, Circle, false);
            handle.rectTransform.sizeDelta = new Vector2(34f, 34f);

            var valueText = Text(rt, format(value), UIStyle.SmallSize, UIStyle.InkSoft, false, TextAlignmentOptions.Right, "Value");
            Layout(valueText, -1f, -1f, 0f, 80f);

            var s = rt.gameObject.AddComponent<Slider>();
            s.transition = Selectable.Transition.None;
            s.targetGraphic = handle;
            s.fillRect = fill.rectTransform;
            s.handleRect = handle.rectTransform;
            s.minValue = min;
            s.maxValue = max;
            s.wholeNumbers = whole;
            s.value = value;
            s.onValueChanged.AddListener(v => { valueText.text = format(v); AudioDirector.Instance?.PlayUI("ui_slider_tick", 0.5f); onChange?.Invoke(v); });
            Layout(s, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, valueText, false);
            return s;
        }

        public static ChoiceSelectable Choice(Transform parent, string label, string[] options, int index, Action<int> onChange)
        {
            var rt = Rect(parent, "Choice " + label);
            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = Rounded;
            bg.type = UnityEngine.UI.Image.Type.Sliced;
            bg.color = UIStyle.PearlDeep;
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(28, 22, 8, 8);
            h.spacing = 10;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            var t = Text(rt, label, UIStyle.BodySize, UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            Layout(t, -1f, -1f, 1f);
            var left = Image(rt, "Prev", UIStyle.InkSoft, Arrow, false);
            left.rectTransform.localScale = new Vector3(-1f, 1f, 1f);
            Layout(left, 28f, 28f, 0f, 28f);
            var value = Text(rt, options[Mathf.Clamp(index, 0, options.Length - 1)], UIStyle.SmallSize + 2f, UIStyle.Teal, false, TextAlignmentOptions.Center, "Value");
            value.fontStyle = FontStyles.Bold;
            Layout(value, -1f, -1f, 0f, 300f);
            var right = Image(rt, "Next", UIStyle.InkSoft, Arrow, false);
            Layout(right, 28f, 28f, 0f, 28f);
            var c = rt.gameObject.AddComponent<ChoiceSelectable>();
            c.transition = Selectable.Transition.None;
            c.targetGraphic = bg;
            c.Init(options, index, value, onChange);
            Layout(c, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, value, false);
            return c;
        }

        public static RectTransform Row(Transform parent, string name, float spacing = 12f)
        {
            var rt = Rect(parent, name);
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.spacing = spacing;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = true;
            h.childForceExpandHeight = false;
            return rt;
        }

        public static void Spacer(Transform parent, float height)
        {
            var rt = Rect(parent, "Spacer");
            Layout(rt.gameObject.AddComponent<LayoutElement>(), height, height);
        }
    }
}
