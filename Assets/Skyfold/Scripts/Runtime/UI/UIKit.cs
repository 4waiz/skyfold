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
        static Sprite s_Rounded, s_Circle, s_Check, s_Cross, s_Arrow, s_Ring, s_Radio, s_Shadow, s_Glow;

        /// <summary>Slider knob diameter and rail thickness (reference pixels).</summary>
        public const float KnobSize = 28f, RailHeight = 10f;
        /// <summary>How far a panel's soft shadow spreads past its edge.</summary>
        public const float ShadowSpread = 26f;

        // Rounded is drawn at twice the canvas resolution (sprite PPU 200 against the canvas's 100) and
        // every sprite is mipmapped with trilinear filtering, so corners and knobs stay smooth on HiDPI
        // laptops, when scaled down, and on VR world-space panels.
        public static Sprite Rounded => s_Rounded != null ? s_Rounded : (s_Rounded = MakeRounded(192, 60));
        public static Sprite Circle => s_Circle != null ? s_Circle : (s_Circle = MakeCircle(256, false));
        public static Sprite Ring => s_Ring != null ? s_Ring : (s_Ring = MakeCircle(256, true));
        public static Sprite Check => s_Check != null ? s_Check : (s_Check = MakeIcon(128, true));
        public static Sprite Cross => s_Cross != null ? s_Cross : (s_Cross = MakeIcon(128, false));
        public static Sprite Arrow => s_Arrow != null ? s_Arrow : (s_Arrow = MakeArrow(128));
        /// <summary>Broadcast glyph (mast, dot, two pairs of arcs) for Noor's radio badge.</summary>
        public static Sprite Radio => s_Radio != null ? s_Radio : (s_Radio = MakeRadio(128));
        /// <summary>9-sliced soft drop shadow for panels (blurred rounded rectangle).</summary>
        public static Sprite SoftShadow => s_Shadow != null ? s_Shadow : (s_Shadow = MakeShadow(160, 30, (int)ShadowSpread));
        /// <summary>Radial soft dot: knob shadows and the backdrop behind the title.</summary>
        public static Sprite Glow => s_Glow != null ? s_Glow : (s_Glow = MakeGlow(128));

        // ------------------------------------------------------------------ procedural sprites
        static Texture2D NewTexture(int size, string name) =>
            new Texture2D(size, size, TextureFormat.RGBA32, true) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 2, name = name };

        static Sprite MakeRounded(int size, int radius)
        {
            var tex = NewTexture(size, "UI Rounded");
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
            tex.Apply(true, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 200f, 0, SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
        }

        static Sprite MakeCircle(int size, bool ring)
        {
            var tex = NewTexture(size, ring ? "UI Ring" : "UI Circle");
            var px = new Color32[size * size];
            float r = size * 0.5f - 1.5f;
            float edge = size / 128f; // keep a ~1 px anti-aliased rim once mipmapped down to icon sizes
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(size * 0.5f, size * 0.5f));
                    float a = Mathf.Clamp01((r - d) / edge + 0.5f);
                    if (ring) a *= Mathf.Clamp01((d - (r - size * 0.11f)) / edge + 0.5f);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(true, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        static Sprite MakeShadow(int size, int radius, int spread)
        {
            var tex = NewTexture(size, "UI Soft Shadow");
            var px = new Color32[size * size];
            // Signed distance to a rounded rectangle inset by `spread`, faded with a smooth falloff.
            float half = size * 0.5f;
            float box = half - spread - radius;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float qx = Mathf.Abs(x + 0.5f - half) - box, qy = Mathf.Abs(y + 0.5f - half) - box;
                    float outside = new Vector2(Mathf.Max(qx, 0f), Mathf.Max(qy, 0f)).magnitude;
                    float d = outside + Mathf.Min(Mathf.Max(qx, qy), 0f) - radius;
                    float t = Mathf.Clamp01((d + spread * 0.35f) / (spread * 1.35f));
                    float a = 1f - t * t * (3f - 2f * t);
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * a * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(true, true);
            float border = spread + radius + 2f;
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect, new Vector4(border, border, border, border));
        }

        static Sprite MakeGlow(int size)
        {
            var tex = NewTexture(size, "UI Glow");
            var px = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(size * 0.5f, size * 0.5f)) / (size * 0.5f);
                    float t = Mathf.Clamp01(d);
                    float a = (1f - t * t) * (1f - t * t); // wide, soft falloff that reaches zero at the edge
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(Mathf.Clamp01(a) * 255));
                }
            tex.SetPixels32(px);
            tex.Apply(true, true);
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

        static Sprite MakeRadio(int size)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "UI Radio" };
            var px = new Color32[size * size];
            var c = new Vector2(0.5f, 0.56f);
            const float w = 0.034f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x + 0.5f, y + 0.5f) / size;
                    Vector2 v = p - c;
                    float d = Mathf.Abs(v.magnitude - 0.075f) - 0.04f;                                // dot
                    d = Mathf.Min(d, SegmentDistance(p, new Vector2(0.5f, 0.2f), new Vector2(0.5f, 0.48f)) - w); // mast
                    d = Mathf.Min(d, SegmentDistance(p, new Vector2(0.38f, 0.2f), new Vector2(0.62f, 0.2f)) - w); // foot
                    // Arcs only within 50 degrees of horizontal, on both sides.
                    float ang = Mathf.Abs(Mathf.Atan2(v.y, Mathf.Abs(v.x))) * Mathf.Rad2Deg;
                    if (ang < 50f)
                    {
                        d = Mathf.Min(d, Mathf.Abs(v.magnitude - 0.2f) - w);
                        d = Mathf.Min(d, Mathf.Abs(v.magnitude - 0.32f) - w);
                    }
                    float a = Mathf.Clamp01(-d * size + 0.5f);
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
            img.type = sliced && img.sprite.border.sqrMagnitude > 0f ? UnityEngine.UI.Image.Type.Sliced : UnityEngine.UI.Image.Type.Simple;
            img.pixelsPerUnitMultiplier = 1f;
            img.color = color;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>Fixed-size rect centred in its parent (knobs, switches): it never stretches with the layout.</summary>
        public static void Centered(RectTransform rt, Vector2 size)
        {
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = size;
            rt.anchoredPosition = Vector2.zero;
        }

        /// <summary>Full-width bar of a fixed height, vertically centred in its parent (slider rails).</summary>
        static void CenterBar(RectTransform rt, float height)
        {
            rt.anchorMin = new Vector2(0f, 0.5f);
            rt.anchorMax = new Vector2(1f, 0.5f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(0f, height);
            rt.anchoredPosition = Vector2.zero;
        }

        public static RectTransform Panel(Transform parent, string name, Color color, float padding = 32f, float spacing = UIStyle.Gap, bool shadow = true)
        {
            var root = Rect(parent, name);
            // Children draw over their parent, so the shadow and the panel face are both children, shadow
            // first: drawing the shadow as a child of a panel-coloured root would grey the whole panel.
            if (shadow)
            {
                var sh = Image(root, "Shadow", new Color(0.03f, 0.07f, 0.09f, 0.34f), SoftShadow);
                var srt = sh.rectTransform;
                srt.anchorMin = Vector2.zero;
                srt.anchorMax = Vector2.one;
                srt.offsetMin = new Vector2(-ShadowSpread, -ShadowSpread - 12f);
                srt.offsetMax = new Vector2(ShadowSpread, ShadowSpread - 12f);
                sh.gameObject.AddComponent<LayoutElement>().ignoreLayout = true;
            }
            var bg = Image(root, "Background", color, Rounded);
            Stretch(bg.rectTransform);
            bg.raycastTarget = true; // the panel face still blocks clicks and XR rays to the world behind it
            bg.gameObject.AddComponent<LayoutElement>().ignoreLayout = true;
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
            bg.color = primary ? UIStyle.PrimarySoft : UIStyle.PearlDeep;
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
            var t = Text(rt, label, UIStyle.BodySize, primary ? UIStyle.Teal : UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            t.fontStyle = FontStyles.Bold;
            TextMeshProUGUI d = null;
            if (!string.IsNullOrEmpty(detail))
            {
                d = Text(rt, detail, UIStyle.SmallSize, primary ? UIStyle.Teal : UIStyle.InkSoft, false, TextAlignmentOptions.Right, "Detail");
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
            h.spacing = 16;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            var t = Text(rt, label, UIStyle.BodySize, UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            Layout(t, -1f, -1f, 1f);

            // Switch: a pill track with a white knob that slides across (fixed size, so it never stretches).
            var sw = Rect(rt, "Switch");
            Layout(sw, 34f, 34f, 0f, 64f);
            var track = Image(sw, "Track", UIStyle.Rail, Rounded);
            Centered(track.rectTransform, new Vector2(64f, 34f));
            var knobShadow = Image(track.rectTransform, "Knob Shadow", new Color(0.02f, 0.08f, 0.1f, 0.4f), Glow, false);
            Centered(knobShadow.rectTransform, new Vector2(34f, 34f));
            var knob = Image(track.rectTransform, "Knob", UIStyle.Knob, Circle, false);
            Centered(knob.rectTransform, new Vector2(26f, 26f));
            knob.preserveAspect = true;
            var state = Text(rt, value ? "On" : "Off", UIStyle.SmallSize, UIStyle.InkSoft, false, TextAlignmentOptions.Right, "State");
            Layout(state, -1f, -1f, 0f, 56f);

            var vis = rt.gameObject.AddComponent<SwitchVisual>();
            vis.track = track;
            vis.knob = knob;
            vis.knobShadow = knobShadow;
            vis.state = state;
            vis.travel = 15f;
            vis.Init(value);

            var tg = rt.gameObject.AddComponent<Toggle>();
            tg.transition = Selectable.Transition.None;
            tg.targetGraphic = bg;
            tg.isOn = value;
            tg.onValueChanged.AddListener(v => { vis.SetOn(v); AudioDirector.Instance?.PlayUI("ui_toggle"); onChange?.Invoke(v); });
            Layout(tg, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, null, false, null, vis.SetActive);
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
            h.spacing = 26; // room for the knob to overhang the rail ends
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = false;
            var t = Text(rt, label, UIStyle.BodySize, UIStyle.Ink, false, TextAlignmentOptions.Left, "Label");
            Layout(t, -1f, -1f, 1f);

            var track = Rect(rt, "Track");
            Layout(track, 40f, 40f, 0f, 260f);
            var rail = Image(track, "Rail", UIStyle.Rail, Rounded);
            CenterBar(rail.rectTransform, RailHeight);
            var fillArea = Rect(track, "Fill Area");
            CenterBar(fillArea, RailHeight);
            var fill = Image(fillArea, "Fill", UIStyle.Teal, Rounded);
            fill.rectTransform.anchorMin = Vector2.zero;
            fill.rectTransform.anchorMax = new Vector2(0f, 1f);
            fill.rectTransform.offsetMin = fill.rectTransform.offsetMax = Vector2.zero;

            // The Slider drives the Handle's anchors and stretches it to the full track height, so the
            // visible knob is a fixed-size centred child: a true circle at any row height or DPI.
            var handleArea = Rect(track, "Handle Area");
            Stretch(handleArea);
            var handle = Rect(handleArea, "Handle");
            handle.anchorMin = Vector2.zero;
            handle.anchorMax = new Vector2(0f, 1f);
            handle.sizeDelta = new Vector2(KnobSize, 0f);
            var knobShadow = Image(handle, "Knob Shadow", new Color(0.02f, 0.08f, 0.1f, 0.42f), Glow, false);
            Centered(knobShadow.rectTransform, new Vector2(KnobSize + 10f, KnobSize + 10f));
            knobShadow.rectTransform.anchoredPosition = new Vector2(0f, -2f);
            var knob = Image(handle, "Knob", UIStyle.Knob, Circle, false);
            Centered(knob.rectTransform, new Vector2(KnobSize, KnobSize));
            knob.preserveAspect = true;
            var ring = Image(knob.rectTransform, "Ring", UIStyle.Teal, Ring, false);
            Stretch(ring.rectTransform);
            ring.preserveAspect = true;

            var valueText = Text(rt, format(value), UIStyle.SmallSize, UIStyle.InkSoft, false, TextAlignmentOptions.Right, "Value");
            Layout(valueText, -1f, -1f, 0f, 84f);

            var s = rt.gameObject.AddComponent<RowSlider>();
            s.hitArea = track;
            s.transition = Selectable.Transition.None;
            s.targetGraphic = knob;
            s.fillRect = fill.rectTransform;
            s.handleRect = handle;
            s.direction = UnityEngine.UI.Slider.Direction.LeftToRight;
            s.minValue = min;
            s.maxValue = max;
            s.wholeNumbers = whole;
            s.value = value;
            // One soft tick per 5% of travel feels like detents; a tick on every drag frame was a buzz.
            float tickStep = whole ? Mathf.Max(1f, (max - min) * 0.05f) : (max - min) * 0.05f;
            float lastTick = s.value;
            s.onValueChanged.AddListener(v =>
            {
                valueText.text = format(v);
                if (Mathf.Abs(v - lastTick) >= tickStep * 0.999f || Mathf.Approximately(v, min) || Mathf.Approximately(v, max))
                {
                    if (!Mathf.Approximately(v, lastTick)) AudioDirector.Instance?.PlayUI("ui_slider_tick", 0.5f);
                    lastTick = v;
                }
                onChange?.Invoke(v);
            });
            Layout(s, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, valueText, false, null, active =>
            {
                // On the teal focus row the teal fill would vanish: switch to the glow tone and a light rail.
                rail.color = active ? new Color(1f, 1f, 1f, 0.3f) : UIStyle.Rail;
                fill.color = active ? UIStyle.TealGlow : UIStyle.Teal;
                ring.color = active ? UIStyle.TealGlow : UIStyle.Teal;
                var k = Vector3.one * (active ? 1.12f : 1f);
                knob.rectTransform.localScale = k;
                knobShadow.rectTransform.localScale = k;
            });
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
            left.preserveAspect = true; // the row layout stretches it to the row height; keep the chevron square
            Layout(left, 28f, 28f, 0f, 28f);
            var value = Text(rt, options[Mathf.Clamp(index, 0, options.Length - 1)], UIStyle.SmallSize + 2f, UIStyle.Teal, false, TextAlignmentOptions.Center, "Value");
            value.fontStyle = FontStyles.Bold;
            Layout(value, -1f, -1f, 0f, 300f);
            var right = Image(rt, "Next", UIStyle.InkSoft, Arrow, false);
            right.preserveAspect = true;
            Layout(right, 28f, 28f, 0f, 28f);
            var c = rt.gameObject.AddComponent<ChoiceSelectable>();
            c.transition = Selectable.Transition.None;
            c.targetGraphic = bg;
            c.Init(options, index, value, onChange, left.rectTransform, right.rectTransform);
            Layout(c, UIStyle.ButtonHeight, UIStyle.ButtonHeight);
            var fx = rt.gameObject.AddComponent<SelectableFX>();
            fx.Init(bg, t, value, false, UIStyle.Teal, active => left.color = right.color = active ? UIStyle.Pearl : UIStyle.InkSoft);
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
