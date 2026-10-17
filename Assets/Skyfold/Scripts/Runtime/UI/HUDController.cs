using TMPro;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace Skyfold
{
    /// <summary>
    /// In-game HUD. Desktop: objective card, storm timer, prompts, hints, subtitles with Noor's radio
    /// portrait, guide arrow. VR: a lazy-follow panel for subtitles/prompts/hints plus a wrist panel
    /// (Y). While VR is active the desktop canvas becomes the spectator overlay on the laptop.
    /// </summary>
    public sealed class HUDController : MonoBehaviour
    {
        public static HUDController Instance { get; private set; }

        public Sprite noorPortrait;
        public Transform wristAnchorOverride;

        Canvas m_Canvas;
        RectTransform m_Root;
        CanvasGroup m_Group;
        RectTransform m_ObjectiveCard, m_TimerCard, m_PromptCard, m_HintCard, m_ToastCard, m_SubCard, m_Badge, m_Arrow, m_Speed, m_CursorHint;
        TextMeshProUGUI m_ObjEpisode, m_ObjText, m_ObjKeys, m_Timer, m_TimerLabel, m_Prompt, m_Hint, m_Toast, m_SubSpeaker, m_SubText, m_SpeedText, m_CursorText;
        Image m_Crosshair, m_TimerBg, m_Portrait, m_RadioGlyph;
        float m_ToastTime, m_HintTime;
        bool m_ObjectivesCollapsed;

        // VR
        Canvas m_VRPanel, m_Wrist;
        RectTransform m_VRSubCard, m_VRPromptCard, m_VRHintCard;
        TextMeshProUGUI m_VRSub, m_VRSpeaker, m_VRPrompt, m_VRHint, m_WristObj, m_WristTimer, m_WristKeys;
        bool m_WristVisible = true;
        float m_WristShowUntil;
        Vector3 m_PanelVel;

        void Awake()
        {
            Instance = this;
            BuildDesktop();
            BuildVR();
        }

        void OnEnable()
        {
            HUDMessages.ToastRequested += OnToast;
            HUDMessages.HintChanged += OnContextHint;
            HUDMessages.CursorHintChanged += OnCursorHint;
        }

        void OnDisable()
        {
            HUDMessages.ToastRequested -= OnToast;
            HUDMessages.HintChanged -= OnContextHint;
            HUDMessages.CursorHintChanged -= OnCursorHint;
        }

        void Start()
        {
            var d = DialogueDirector.Instance;
            if (d != null) { d.LineStarted += OnLine; d.LineEnded += OnLineEnded; }
            var m = MissionDirector.Instance;
            if (m != null) { m.ObjectiveChanged += OnObjective; m.HintShown += OnHint; }
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            var d = DialogueDirector.Instance;
            if (d != null) { d.LineStarted -= OnLine; d.LineEnded -= OnLineEnded; }
            var m = MissionDirector.Instance;
            if (m != null) { m.ObjectiveChanged -= OnObjective; m.HintShown -= OnHint; }
        }

        // ------------------------------------------------------------------ construction
        RectTransform Card(string name, Vector2 anchor, Vector2 pivot, Vector2 pos, float width, Color color, out TextMeshProUGUI text, float size = 28f)
        {
            var rt = UIKit.Rect(m_Root, name);
            rt.anchorMin = rt.anchorMax = anchor;
            rt.pivot = pivot;
            rt.anchoredPosition = pos;
            CardFace(rt, color);
            var v = rt.gameObject.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(26, 26, 16, 18);
            v.spacing = 4;
            v.childControlHeight = v.childControlWidth = true;
            v.childForceExpandHeight = false;
            var fit = rt.gameObject.AddComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            rt.sizeDelta = new Vector2(width, 0f);
            text = UIKit.Text(rt, "", size, UIStyle.Ink);
            return rt;
        }

        /// <summary>
        /// A card's soft shadow and face as layout-ignored children (shadow first), so the shadow sits under
        /// the card instead of tinting it. Returns the face image for colour changes.
        /// </summary>
        static Image CardFace(RectTransform card, Color color)
        {
            var sh = UIKit.Image(card, "Shadow", new Color(0.03f, 0.07f, 0.09f, 0.24f), UIKit.SoftShadow);
            sh.rectTransform.anchorMin = Vector2.zero;
            sh.rectTransform.anchorMax = Vector2.one;
            sh.rectTransform.offsetMin = new Vector2(-UIKit.ShadowSpread, -UIKit.ShadowSpread - 6f);
            sh.rectTransform.offsetMax = new Vector2(UIKit.ShadowSpread, UIKit.ShadowSpread - 6f);
            sh.gameObject.AddComponent<LayoutElement>().ignoreLayout = true;
            var face = UIKit.Image(card, "Background", color, UIKit.Rounded);
            UIKit.Stretch(face.rectTransform);
            face.gameObject.AddComponent<LayoutElement>().ignoreLayout = true;
            return face;
        }

        void BuildDesktop()
        {
            m_Canvas = UIKit.ScreenCanvas("HUD Canvas", 20, transform);
            m_Canvas.GetComponent<GraphicRaycaster>().enabled = false;
            m_Root = UIKit.Rect(m_Canvas.transform, "Root");
            UIKit.Stretch(m_Root);
            m_Group = m_Root.gameObject.AddComponent<CanvasGroup>();
            m_Group.interactable = false;
            m_Group.blocksRaycasts = false;

            m_ObjectiveCard = Card("Objective", new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(40f, -40f), 560f, UIStyle.PanelGlass, out m_ObjEpisode, 20f);
            m_ObjEpisode.color = UIStyle.Teal;
            m_ObjEpisode.fontStyle = FontStyles.Bold;
            m_ObjText = UIKit.Text(m_ObjectiveCard, "", 30f, UIStyle.Ink);
            m_ObjKeys = UIKit.Text(m_ObjectiveCard, "", 20f, UIStyle.InkSoft);

            m_TimerCard = Card("Timer", new Vector2(1f, 1f), new Vector2(1f, 1f), new Vector2(-40f, -40f), 240f, UIStyle.PanelGlass, out m_TimerLabel, 18f);
            m_TimerBg = m_TimerCard.Find("Background").GetComponent<Image>();
            m_TimerLabel.text = "STORM ARRIVES IN";
            m_TimerLabel.color = UIStyle.InkSoft;
            m_TimerLabel.characterSpacing = 2f;
            m_Timer = UIKit.Text(m_TimerCard, "5:00", 48f, UIStyle.Ink, true);

            m_PromptCard = Card("Prompt", new Vector2(0.5f, 0f), new Vector2(0.5f, 0f), new Vector2(0f, 300f), 640f, new Color(0.13f, 0.2f, 0.23f, 0.86f), out m_Prompt, 28f);
            m_Prompt.color = UIStyle.Pearl;
            m_Prompt.alignment = TextAlignmentOptions.Center;

            m_HintCard = Card("Hint", new Vector2(0.5f, 0f), new Vector2(0.5f, 0f), new Vector2(0f, 380f), 820f, new Color(0.99f, 0.95f, 0.85f, 0.95f), out m_Hint, 26f);
            m_Hint.alignment = TextAlignmentOptions.Center;

            m_ToastCard = Card("Toast", new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -150f), 820f, UIStyle.PanelGlass, out m_Toast, 28f);
            m_Toast.alignment = TextAlignmentOptions.Center;

            // Subtitles with Noor's radio portrait.
            m_SubCard = UIKit.Rect(m_Root, "Subtitles");
            m_SubCard.anchorMin = m_SubCard.anchorMax = new Vector2(0.5f, 0f);
            m_SubCard.pivot = new Vector2(0.5f, 0f);
            m_SubCard.anchoredPosition = new Vector2(0f, 48f);
            CardFace(m_SubCard, new Color(0.1f, 0.16f, 0.19f, 0.88f));
            var h = m_SubCard.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(18, 30, 16, 16);
            h.spacing = 20;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlHeight = h.childControlWidth = true;
            h.childForceExpandWidth = false;
            var fit = m_SubCard.gameObject.AddComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            fit.horizontalFit = ContentSizeFitter.FitMode.PreferredSize;
            m_Portrait = UIKit.Image(m_SubCard, "Portrait", UIStyle.TealLight, UIKit.Circle, false);
            UIKit.Layout(m_Portrait, 96f, 96f, 0f, 96f);
            // Until a portrait image exists, the badge shows an original broadcast glyph (no likeness).
            m_RadioGlyph = UIKit.Image(m_Portrait.rectTransform, "Radio Glyph", new Color(0.06f, 0.27f, 0.3f), UIKit.Radio, false);
            m_RadioGlyph.rectTransform.anchorMin = new Vector2(0.16f, 0.16f);
            m_RadioGlyph.rectTransform.anchorMax = new Vector2(0.84f, 0.84f);
            m_RadioGlyph.rectTransform.offsetMin = m_RadioGlyph.rectTransform.offsetMax = Vector2.zero;
            var col = UIKit.Rect(m_SubCard, "Text");
            var cv = col.gameObject.AddComponent<VerticalLayoutGroup>();
            cv.childControlHeight = cv.childControlWidth = true;
            cv.childForceExpandHeight = false;
            cv.spacing = 2;
            UIKit.Layout(col, -1f, -1f, 0f, 1100f);
            m_SubSpeaker = UIKit.Text(col, "Noor · radio", 20f, UIStyle.TealGlow);
            m_SubSpeaker.fontStyle = FontStyles.Bold;
            m_SubText = UIKit.Text(col, "", 30f, UIStyle.Pearl);

            m_Crosshair = UIKit.Image(m_Root, "Crosshair", new Color(1f, 1f, 1f, 0.7f), UIKit.Circle, false);
            m_Crosshair.rectTransform.anchorMin = m_Crosshair.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
            m_Crosshair.rectTransform.sizeDelta = new Vector2(8f, 8f);

            var arrowImg = UIKit.Image(m_Root, "Guide Arrow", UIStyle.Gold, UIKit.Arrow, false);
            m_Arrow = arrowImg.rectTransform;
            m_Arrow.sizeDelta = new Vector2(64f, 64f);

            m_Speed = Card("Speed", new Vector2(1f, 0f), new Vector2(1f, 0f), new Vector2(-40f, 48f), 220f, UIStyle.PanelGlass, out m_SpeedText, 34f);
            m_SpeedText.alignment = TextAlignmentOptions.Center;

            m_Badge = Card("Spectator Badge", new Vector2(1f, 0f), new Vector2(1f, 0f), new Vector2(-40f, 48f), 330f, new Color(0.06f, 0.43f, 0.45f, 0.92f), out var badgeText, 22f);
            badgeText.text = "<b>LIVE · VR</b>   SKYFOLD\n<size=16>Hobby build · F5 operator reset (demo)</size>";
            badgeText.color = UIStyle.Pearl;

            m_CursorHint = Card("Cursor Hint", new Vector2(0.5f, 0f), new Vector2(0.5f, 0f), new Vector2(0f, 220f), 620f, UIStyle.PanelGlass, out m_CursorText, 22f);
            m_CursorText.alignment = TextAlignmentOptions.Center;

            HideAllCards();
        }

        void HideAllCards()
        {
            foreach (var c in new[] { m_PromptCard, m_HintCard, m_ToastCard, m_SubCard, m_Speed, m_Badge, m_CursorHint })
                if (c != null) c.gameObject.SetActive(false);
        }

        Canvas WorldCanvas(string name, Vector2 size, float scale)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(transform, false);
            var c = go.AddComponent<Canvas>();
            c.renderMode = RenderMode.WorldSpace;
            ((RectTransform)go.transform).sizeDelta = size;
            go.transform.localScale = Vector3.one * scale;
            go.AddComponent<TrackedDeviceGraphicRaycaster>().enabled = false;
            return c;
        }

        RectTransform VRCard(Transform parent, string name, Color color, out TextMeshProUGUI text, float size)
        {
            var rt = UIKit.Rect(parent, name);
            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = UIKit.Rounded;
            bg.type = Image.Type.Sliced;
            bg.color = color;
            var v = rt.gameObject.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(26, 26, 14, 16);
            v.childControlHeight = v.childControlWidth = true;
            v.childForceExpandHeight = false;
            text = UIKit.Text(rt, "", size, UIStyle.Ink, false, TextAlignmentOptions.Center);
            return rt;
        }

        void BuildVR()
        {
            m_VRPanel = WorldCanvas("VR Lazy Panel", new Vector2(900f, 520f), 0.0011f);
            var root = (RectTransform)m_VRPanel.transform;
            var v = root.gameObject.AddComponent<VerticalLayoutGroup>();
            v.childAlignment = TextAnchor.LowerCenter;
            v.spacing = 12;
            v.childControlHeight = v.childControlWidth = true;
            v.childForceExpandHeight = false;
            m_VRHintCard = VRCard(root, "Hint", new Color(0.99f, 0.95f, 0.85f, 0.95f), out m_VRHint, 30f);
            m_VRPromptCard = VRCard(root, "Prompt", new Color(0.13f, 0.2f, 0.23f, 0.9f), out m_VRPrompt, 32f);
            m_VRPrompt.color = UIStyle.Pearl;
            m_VRSubCard = VRCard(root, "Subtitles", new Color(0.1f, 0.16f, 0.19f, 0.9f), out m_VRSpeaker, 22f);
            m_VRSpeaker.color = UIStyle.TealGlow;
            m_VRSpeaker.alignment = TextAlignmentOptions.Left;
            m_VRSub = UIKit.Text(m_VRSubCard, "", 34f, UIStyle.Pearl);
            m_VRPanel.gameObject.SetActive(false);

            m_Wrist = WorldCanvas("VR Wrist Panel", new Vector2(420f, 260f), 0.0005f);
            var w = (RectTransform)m_Wrist.transform;
            var bg = w.gameObject.AddComponent<Image>();
            bg.sprite = UIKit.Rounded;
            bg.type = Image.Type.Sliced;
            bg.color = UIStyle.PanelGlass;
            var wv = w.gameObject.AddComponent<VerticalLayoutGroup>();
            wv.padding = new RectOffset(22, 22, 16, 16);
            wv.spacing = 6;
            wv.childControlHeight = wv.childControlWidth = true;
            wv.childForceExpandHeight = false;
            m_WristTimer = UIKit.Text(w, "", 40f, UIStyle.Ink, true);
            m_WristObj = UIKit.Text(w, "", 30f, UIStyle.Ink);
            m_WristKeys = UIKit.Text(w, "", 22f, UIStyle.InkSoft);
            m_Wrist.gameObject.SetActive(false);
        }

        // ------------------------------------------------------------------ events
        void OnToast(string text, bool warning)
        {
            m_Toast.text = (warning ? "<color=#F2714B><b>Not quite.</b></color>  " : "") + text;
            m_ToastTime = warning ? 4.5f : 3.2f;
            m_ToastCard.gameObject.SetActive(true);
            if (m_VRHint != null) { m_VRHint.text = text; m_HintTime = Mathf.Max(m_HintTime, m_ToastTime); }
        }

        void OnContextHint(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            m_Hint.text = text;
            m_VRHint.text = text;
            m_HintTime = 0.5f;
        }

        void OnCursorHint(string text)
        {
            m_CursorHint.gameObject.SetActive(!string.IsNullOrEmpty(text) && PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.Desktop);
            m_CursorText.text = text ?? "";
        }

        void OnHint(string hint)
        {
            m_Hint.text = "<b>Hint</b>  " + hint;
            m_VRHint.text = "Hint: " + hint;
            m_HintTime = 9f;
        }

        void OnLine(VoLine line, float duration)
        {
            if (!SettingsStore.Current.subtitles) return;
            string speaker = line.speaker == "nuri" ? "NURI" : "Noor · radio";
            m_SubSpeaker.text = speaker;
            m_SubText.text = line.text;
            m_SubText.fontSize = 30f * SettingsStore.Current.subtitleScale;
            m_SubCard.gameObject.SetActive(true);
            m_VRSpeaker.text = speaker;
            m_VRSub.text = line.text;
            m_VRSub.fontSize = 34f * SettingsStore.Current.subtitleScale;
            bool nuri = line.speaker == "nuri";
            if (noorPortrait != null && !nuri) { m_Portrait.sprite = noorPortrait; m_Portrait.color = Color.white; }
            else { m_Portrait.sprite = UIKit.Circle; m_Portrait.color = nuri ? UIStyle.Gold : UIStyle.TealLight; }
            if (m_RadioGlyph != null) m_RadioGlyph.gameObject.SetActive(noorPortrait == null && !nuri);
        }

        void OnLineEnded(VoLine line)
        {
            m_SubCard.gameObject.SetActive(false);
            m_VRSub.text = "";
        }

        void OnObjective(ObjectiveDef o, int index)
        {
            m_WristShowUntil = Time.unscaledTime + 5f;
        }

        public void ToggleObjectives()
        {
            if (PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.VR) m_WristVisible = !m_WristVisible;
            else m_ObjectivesCollapsed = !m_ObjectivesCollapsed;
            AudioDirector.Instance?.PlayUI("ui_toggle", 0.6f);
        }

        // ------------------------------------------------------------------ per frame
        void LateUpdate()
        {
            var root = GameRoot.Instance;
            var md = MissionDirector.Instance;
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            if (root == null || md == null || rigs == null || input == null) return;
            bool vr = rigs.Mode == PlayMode.VR;
            bool playing = root.IsPlaying && md.Current != null && !root.IsPaused && md.State != MissionState.Results;
            m_Root.gameObject.SetActive(playing || m_SubCard.gameObject.activeSelf);

            m_ToastTime -= Time.unscaledDeltaTime;
            if (m_ToastTime <= 0f && m_ToastCard.gameObject.activeSelf) m_ToastCard.gameObject.SetActive(false);
            m_HintTime -= Time.unscaledDeltaTime;
            bool showHint = m_HintTime > 0f || !string.IsNullOrEmpty(HUDMessages.Hint);
            if (!string.IsNullOrEmpty(HUDMessages.Hint) && m_HintTime <= 0f) { m_Hint.text = HUDMessages.Hint; m_VRHint.text = HUDMessages.Hint; }
            m_HintCard.gameObject.SetActive(playing && showHint);

            // Objective + timer.
            var o = md.CurrentObjective;
            if (md.Current != null)
            {
                m_ObjEpisode.text = (md.Current.IsDemo ? "DEMO" : "EPISODE " + md.Current.Episode) + "  ·  " + md.Current.Title.ToUpperInvariant();
                string text = o != null ? o.CardText(rigs.Mode) : (md.State == MissionState.Success ? "Complete!" : "");
                if (o?.Progress != null) text += "  <color=#0F6F73>" + o.Progress(md.Ctx) + "</color>";
                m_ObjText.text = text;
                m_ObjText.gameObject.SetActive(!m_ObjectivesCollapsed);
                m_ObjKeys.text = KeyLine(input, rigs);
                m_ObjKeys.gameObject.SetActive(!m_ObjectivesCollapsed && !vr);
            }
            m_ObjectiveCard.gameObject.SetActive(playing);
            float left = md.StormLeft;
            int mm = Mathf.FloorToInt(left / 60f), ss = Mathf.FloorToInt(left % 60f);
            m_Timer.text = $"{mm}:{ss:00}";
            bool held = md.StormHeld && md.State == MissionState.Active;
            m_TimerLabel.text = held ? "STORM WAITS WHILE YOU LEARN" : "STORM ARRIVES IN";
            Color tc = left < 30f ? UIStyle.Coral : (left < 60f ? new Color(0.85f, 0.45f, 0.3f) : UIStyle.Ink);
            m_Timer.color = tc;
            m_TimerBg.color = left < 30f ? new Color(1f, 0.9f, 0.86f, 0.96f) : UIStyle.PanelGlass;
            m_TimerCard.gameObject.SetActive(playing);

            // Prompt line.
            string prompt = PromptText(input, rigs);
            m_PromptCard.gameObject.SetActive(playing && !vr && !string.IsNullOrEmpty(prompt));
            m_Prompt.text = prompt ?? "";
            m_Crosshair.gameObject.SetActive(playing && !vr && rigs.desktop != null && rigs.desktop.View == DesktopView.FirstPerson);

            // Car speed.
            var car = CourierVehicle.Instance;
            bool driving = playing && car != null && car.HasDriver && !vr;
            m_Speed.gameObject.SetActive(driving);
            if (driving) m_SpeedText.text = Mathf.RoundToInt(Mathf.Abs(car.Speed) * 3.6f) + " km/h";
            m_Badge.gameObject.SetActive(vr);
            if (vr) m_Speed.gameObject.SetActive(false);

            UpdateArrow(playing && !vr, o, rigs);
            UpdateVR(vr, playing, o, rigs, input, prompt, held, left);
        }

        static string KeyLine(InputRouter input, PlayerRigs rigs)
        {
            switch (input.Context)
            {
                case InputContext.Architect: return Keys("Hold left mouse: move a piece", "R: turn", "Q: fold down", "Tab: hide");
                case InputContext.Driving: return Keys("W/S: drive & brake", "A/D: steer", "E: climb out", "Hold R: back on the road", "Tab: hide");
                default: return Keys("WASD: walk", "E: use", "Q: fold at a station", "Tab: hide");
            }
        }

        /// <summary>Joins key hints so a line only ever wraps between hints, never inside one.</summary>
        static string Keys(params string[] parts)
        {
            for (int i = 0; i < parts.Length; i++) parts[i] = "<nobr>" + parts[i] + "</nobr>";
            return string.Join("   ·   ", parts);
        }

        string PromptText(InputRouter input, PlayerRigs rigs)
        {
            var fold = FoldController.Instance;
            var car = CourierVehicle.Instance;
            bool vr = rigs.Mode == PlayMode.VR;
            if (input.Context == InputContext.Driving || input.Context == InputContext.RemoteDriving)
            {
                if (car != null && Mathf.Abs(car.Speed) < 0.6f) return $"[{input.ExitKeyLabel}]  Climb out";
                return null;
            }
            if (fold != null && fold.InStreet && fold.StationInRange != null) return $"[{input.FoldKeyLabel}]  Fold up to the Atelier";
            if (fold != null && fold.InAtelier && input.Context == InputContext.Architect && !vr) return null;
            if (!vr)
            {
                var scan = FindScanner();
                var cur = scan != null ? scan.Current : null;
                if (cur != null) return cur.CanInteract(InteractorKind.Desktop) ? $"[E]  {cur.Prompt}" : cur.BlockedReason;
            }
            else
            {
                var use = FindVRUse();
                var cur = use != null ? (use.RightTarget ?? use.LeftTarget) : null;
                if (cur != null) return cur.CanInteract(InteractorKind.VRRight) ? $"Trigger:  {cur.Prompt}" : cur.BlockedReason;
                if (fold != null && fold.InAtelier) return $"[X]  Fold down into the street";
            }
            return null;
        }

        DesktopInteractionScanner m_Scanner;
        VRUseHandler m_VRUse;
        DesktopInteractionScanner FindScanner() => m_Scanner != null ? m_Scanner : (m_Scanner = FindAnyObjectByType<DesktopInteractionScanner>());
        VRUseHandler FindVRUse() => m_VRUse != null ? m_VRUse : (m_VRUse = FindAnyObjectByType<VRUseHandler>());

        void UpdateArrow(bool show, ObjectiveDef o, PlayerRigs rigs)
        {
            var target = o != null ? SceneRegistry.Get(o.GuideTarget) : null;
            var cam = rigs.ActiveCamera;
            bool visible = false;
            if (show && target != null && cam != null && FoldController.Instance != null && FoldController.Instance.InStreet)
            {
                Vector3 vp = cam.WorldToViewportPoint(target.position + Vector3.up);
                bool onScreen = vp.z > 0f && vp.x > 0.05f && vp.x < 0.95f && vp.y > 0.08f && vp.y < 0.92f;
                if (!onScreen)
                {
                    Vector2 dir = new Vector2(vp.x - 0.5f, vp.y - 0.5f);
                    if (vp.z < 0f) dir = -dir;
                    if (dir.sqrMagnitude < 0.0001f) dir = Vector2.down;
                    dir.Normalize();
                    var size = ((RectTransform)m_Canvas.transform).rect.size;
                    Vector2 pos = new Vector2(dir.x * (size.x * 0.5f - 80f), dir.y * (size.y * 0.5f - 80f));
                    m_Arrow.anchoredPosition = pos;
                    m_Arrow.localRotation = Quaternion.Euler(0f, 0f, Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg);
                    visible = true;
                }
            }
            m_Arrow.gameObject.SetActive(visible);
        }

        void UpdateVR(bool vr, bool playing, ObjectiveDef o, PlayerRigs rigs, InputRouter input, string prompt, bool held, float left)
        {
            bool showPanel = vr && (playing || m_VRSub.text.Length > 0);
            if (m_VRPanel.gameObject.activeSelf != showPanel) m_VRPanel.gameObject.SetActive(showPanel);
            if (showPanel && rigs.Head != null)
            {
                // Lazy follow: stays put until you look well away, then glides back below your gaze.
                var head = rigs.Head;
                Vector3 fwd = rigs.Forward;
                Vector3 goal = head.position + fwd * 1.3f + Vector3.up * -0.32f;
                var t = m_VRPanel.transform;
                Vector3 toPanel = t.position - head.position;
                float angle = Vector3.Angle(Vector3.ProjectOnPlane(toPanel, Vector3.up), fwd);
                if (angle > 28f || toPanel.magnitude > 2.2f || toPanel.magnitude < 0.6f || m_PanelVel.sqrMagnitude > 0.0001f)
                {
                    t.position = Vector3.SmoothDamp(t.position, goal, ref m_PanelVel, 0.35f, 4f, Time.unscaledDeltaTime);
                    if ((t.position - goal).sqrMagnitude < 0.0004f) m_PanelVel = Vector3.zero;
                }
                t.rotation = Quaternion.LookRotation(t.position - head.position, Vector3.up);
                m_VRSubCard.gameObject.SetActive(m_VRSub.text.Length > 0 && SettingsStore.Current.subtitles);
                m_VRPromptCard.gameObject.SetActive(playing && !string.IsNullOrEmpty(prompt));
                m_VRPrompt.text = prompt ?? "";
                bool hint = m_HintTime > 0f || !string.IsNullOrEmpty(HUDMessages.Hint);
                m_VRHintCard.gameObject.SetActive(playing && hint && m_VRHint.text.Length > 0);
            }

            bool wrist = vr && playing && (m_WristVisible || Time.unscaledTime < m_WristShowUntil);
            if (m_Wrist.gameObject.activeSelf != wrist) m_Wrist.gameObject.SetActive(wrist);
            if (wrist && rigs.vr != null && rigs.vr.LeftHand != null)
            {
                var anchor = wristAnchorOverride != null ? wristAnchorOverride : rigs.vr.LeftHand;
                var t = m_Wrist.transform;
                t.position = anchor.position + anchor.up * 0.06f + anchor.right * 0.02f - anchor.forward * 0.06f;
                t.rotation = Quaternion.LookRotation(t.position - rigs.Head.position, anchor.up);
                int mm = Mathf.FloorToInt(left / 60f), ss = Mathf.FloorToInt(left % 60f);
                m_WristTimer.text = held ? $"{mm}:{ss:00} <size=60%>storm waits</size>" : $"<color={(left < 60f ? "#F2714B" : "#22333B")}>{mm}:{ss:00}</color>";
                string text = o != null ? o.CardText(PlayMode.VR) : "";
                if (o?.Progress != null) text += "  " + o.Progress(MissionDirector.Instance.Ctx);
                m_WristObj.text = text;
                m_WristKeys.text = input.Context == InputContext.Driving ? "B: climb out (stopped) · Menu: pause" : "X: fold at a station · Y: hide · Menu: pause";
            }
        }
    }
}
