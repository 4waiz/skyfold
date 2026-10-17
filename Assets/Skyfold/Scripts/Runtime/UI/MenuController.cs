using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace Skyfold
{
    /// <summary>
    /// Every menu screen, built in code into a desktop overlay canvas or a VR world-space panel.
    /// Keyboard (arrows/WASD, Enter, Esc), mouse and XR controller rays all work.
    /// </summary>
    public sealed class MenuController : MonoBehaviour
    {
        public static MenuController Instance { get; private set; }

        Canvas m_Desktop, m_VR;
        RectTransform m_DesktopRoot, m_VRRoot, m_Wordmark;
        string m_Screen;
        readonly Stack<string> m_History = new Stack<string>();
        Selectable m_First;
        bool m_Compact;
        float m_OpenedAt;

        public bool IsOpen => m_Screen != null;
        public string Screen => m_Screen;

        void Awake()
        {
            Instance = this;
            m_Desktop = UIKit.ScreenCanvas("Menu Canvas", 50, transform);
            m_DesktopRoot = UIKit.Rect(m_Desktop.transform, "Root");
            UIKit.Stretch(m_DesktopRoot);

            var vrGo = new GameObject("VR Menu Canvas", typeof(RectTransform));
            vrGo.transform.SetParent(transform, false);
            vrGo.layer = LayerMask.NameToLayer("WorldUI") >= 0 ? LayerMask.NameToLayer("WorldUI") : 0;
            m_VR = vrGo.AddComponent<Canvas>();
            m_VR.renderMode = RenderMode.WorldSpace;
            m_VR.sortingOrder = 10;
            ((RectTransform)vrGo.transform).sizeDelta = new Vector2(900f, 1150f);
            vrGo.transform.localScale = Vector3.one * 0.0012f;
            vrGo.AddComponent<TrackedDeviceGraphicRaycaster>();
            m_VRRoot = UIKit.Rect(vrGo.transform, "Root");
            UIKit.Stretch(m_VRRoot);
            m_VR.gameObject.SetActive(false);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        bool VRMode => PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.VR;

        // ------------------------------------------------------------------ navigation
        public void Show(string screen, bool push = true)
        {
            if (push && m_Screen != null && m_Screen != screen) m_History.Push(m_Screen);
            m_Screen = screen;
            Build();
        }

        public void Back()
        {
            if (m_Screen == "pause" || m_Screen == "title" || m_Screen == "launcher") { if (m_Screen == "pause") GameRoot.Instance.Resume(); return; }
            if (m_Screen == "results" || m_Screen == "failed" || m_Screen == "vrstart") return;
            SettingsStore.Save();
            m_Screen = m_History.Count > 0 ? m_History.Pop() : null;
            if (m_Screen == null) Close(); else Build();
        }

        public void Close()
        {
            m_Screen = null;
            m_History.Clear();
            Clear(m_DesktopRoot);
            Clear(m_VRRoot);
            m_Desktop.gameObject.SetActive(false);
            m_VR.gameObject.SetActive(false);
            if (EventSystem.current != null) EventSystem.current.SetSelectedGameObject(null);
        }

        public void Refresh() { if (m_Screen != null) Build(); }

        static void Clear(RectTransform root)
        {
            for (int i = root.childCount - 1; i >= 0; i--) Destroy(root.GetChild(i).gameObject);
        }

        void Update()
        {
            if (m_Screen == null) return;
            if (m_PanelRoot != null && (m_PanelRoot.rect.size - m_FittedFor).sqrMagnitude > 1f) FitPanel(); // window resized
            var input = InputRouter.Instance;
            bool escBack = input != null && input.Pause.WasPressedThisFrame() && m_Screen != "pause";
            if (input != null && (input.Back.WasPressedThisFrame() || escBack) && Time.unscaledTime - m_OpenedAt > 0.2f) Back();
            // Keep a focused control for keyboard users.
            var es = EventSystem.current;
            if (!VRMode && es != null && (es.currentSelectedGameObject == null || !es.currentSelectedGameObject.activeInHierarchy) && m_First != null &&
                UnityEngine.InputSystem.Keyboard.current != null && UnityEngine.InputSystem.Keyboard.current.anyKey.wasPressedThisFrame)
                es.SetSelectedGameObject(m_First.gameObject);
        }

        // ------------------------------------------------------------------ build
        void Build()
        {
            Clear(m_DesktopRoot);
            Clear(m_VRRoot);
            m_First = null;
            m_Compact = false;
            m_OpenedAt = Time.unscaledTime;
            bool vr = VRMode;
            m_Desktop.gameObject.SetActive(!vr);
            m_VR.gameObject.SetActive(vr);
            var root = vr ? m_VRRoot : m_DesktopRoot;
            if (vr) PlaceVR();

            bool title = m_Screen == "title" || m_Screen == "launcher" || m_Screen == "episodes";
            if (!vr && !title)
            {
                var scrim = UIKit.Image(root, "Scrim", UIStyle.Scrim, null, false);
                UIKit.Stretch(scrim.rectTransform);
                scrim.sprite = null;
            }
            if (title && !vr) BuildWordmark(root);

            var panel = UIKit.Panel(root, "Panel " + m_Screen, UIStyle.PanelGlass, vr ? 40f : 36f);
            if (vr)
            {
                panel.anchorMin = panel.anchorMax = new Vector2(0.5f, 1f);
                panel.pivot = new Vector2(0.5f, 1f);
                panel.anchoredPosition = new Vector2(0f, -10f);
                panel.sizeDelta = new Vector2(860f, 0f);
            }
            else if (title)
            {
                panel.anchorMin = panel.anchorMax = new Vector2(0f, 1f);
                panel.pivot = new Vector2(0f, 1f);
                panel.anchoredPosition = new Vector2(110f, -262f);
                panel.sizeDelta = new Vector2(740f, 0f); // wide enough for a label plus its detail, and the launcher question, on one line
                var vlg = panel.GetComponent<VerticalLayoutGroup>();
                vlg.spacing = 8f;
                vlg.padding = new RectOffset(24, 24, 24, 24);
                m_Compact = true;
            }
            else
            {
                panel.anchorMin = panel.anchorMax = new Vector2(0.5f, 0.5f);
                panel.pivot = new Vector2(0.5f, 0.5f);
                panel.sizeDelta = new Vector2(m_Screen == "controls" || m_Screen == "credits" ? 1120f : 820f, 0f);
            }

            m_Compact = m_Compact && title && !vr;
            var b = new Builder(panel, this);
            switch (m_Screen)
            {
                case "launcher": BuildLauncher(b); break;
                case "title": BuildTitle(b, vr); break;
                case "episodes": BuildEpisodes(b); break;
                case "controls": BuildControls(b); break;
                case "comfort": BuildComfort(b, vr); break;
                case "audio": BuildAudio(b); break;
                case "display": BuildDisplay(b); break;
                case "credits": BuildCredits(b); break;
                case "quit": BuildQuit(b); break;
                case "pause": BuildPause(b, vr); break;
                case "failed": BuildFailed(b); break;
                case "results": BuildResults(b); break;
                case "vrstart": BuildVRStart(b); break;
                case "vrfail": BuildVRFail(b); break;
                case "firstcomfort": BuildFirstComfort(b); break;
            }

            LayoutRebuilder.ForceRebuildLayoutImmediate(panel);
            m_Panel = panel;
            m_PanelRoot = root;
            m_PanelTop = vr ? 10f : title ? 262f : -1f;
            FitPanel();
            if (m_First != null && EventSystem.current != null) EventSystem.current.SetSelectedGameObject(m_First.gameObject);
        }

        RectTransform m_Panel, m_PanelRoot;
        float m_PanelTop; // distance from the canvas top to a top-anchored panel; -1 when centred
        Vector2 m_FittedFor;

        /// <summary>
        /// Shrinks the panel uniformly when it would not fit the window (short or ultrawide windows, the
        /// VR canvas with its extra comfort rows) instead of letting rows run off the screen.
        /// </summary>
        void FitPanel()
        {
            if (m_Panel == null || m_PanelRoot == null) return;
            var avail = m_PanelRoot.rect.size;
            m_FittedFor = avail;
            const float margin = 28f;
            float h = m_Panel.rect.height, w = m_Panel.rect.width;
            if (h <= 0f || w <= 0f || avail.y <= 0f) return;
            float roomY = m_PanelTop >= 0f ? avail.y - m_PanelTop - margin : avail.y - 2f * margin;
            float roomX = avail.x - 2f * margin;
            float s = Mathf.Clamp(Mathf.Min(roomY / h, roomX / w), 0.6f, 1f);
            m_Panel.localScale = new Vector3(s, s, 1f);
        }

        void BuildWordmark(RectTransform root)
        {
            // Soft dark falloff behind the title so the pearl wordmark and gold subtitle read over a bright sky.
            var backdrop = UIKit.Image(root, "Wordmark Backdrop", new Color(0.03f, 0.08f, 0.1f, 0.5f), UIKit.Glow, false);
            backdrop.rectTransform.anchorMin = backdrop.rectTransform.anchorMax = new Vector2(0f, 1f);
            backdrop.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            backdrop.rectTransform.anchoredPosition = new Vector2(520f, -150f);
            backdrop.rectTransform.sizeDelta = new Vector2(1500f, 560f);

            var w = UIKit.Rect(root, "Wordmark");
            w.anchorMin = w.anchorMax = new Vector2(0f, 1f);
            w.pivot = new Vector2(0f, 1f);
            w.anchoredPosition = new Vector2(110f, -36f);
            w.sizeDelta = new Vector2(1100f, 220f);
            var t = UIKit.Text(w, SkyfoldInfo.Title, UIStyle.TitleSize * 1.25f, UIStyle.Pearl, true);
            t.characterSpacing = 6f;
            t.rectTransform.anchorMin = new Vector2(0f, 0.42f);
            t.rectTransform.anchorMax = Vector2.one;
            t.rectTransform.offsetMin = t.rectTransform.offsetMax = Vector2.zero;
            var outline = t.gameObject.AddComponent<Shadow>();
            outline.effectColor = new Color(0.05f, 0.12f, 0.14f, 0.55f);
            outline.effectDistance = new Vector2(3f, -4f);
            var s = UIKit.Text(w, SkyfoldInfo.Subtitle, UIStyle.HeadingSize, UIStyle.Gold, true);
            s.rectTransform.anchorMin = Vector2.zero;
            s.rectTransform.anchorMax = new Vector2(1f, 0.42f);
            s.rectTransform.offsetMin = s.rectTransform.offsetMax = Vector2.zero;
            s.gameObject.AddComponent<Shadow>().effectColor = new Color(0.05f, 0.12f, 0.14f, 0.5f);

            // Credit line on a small dark pill so it stays readable over the bright terrace.
            var footBg = UIKit.Rect(root, "Footer");
            footBg.anchorMin = footBg.anchorMax = new Vector2(1f, 0f);
            footBg.pivot = new Vector2(1f, 0f);
            footBg.anchoredPosition = new Vector2(-40f, 24f);
            var footImg = footBg.gameObject.AddComponent<Image>();
            footImg.sprite = UIKit.Rounded;
            footImg.type = Image.Type.Sliced;
            footImg.color = new Color(0.1f, 0.16f, 0.19f, 0.62f);
            var footRow = footBg.gameObject.AddComponent<HorizontalLayoutGroup>();
            footRow.padding = new RectOffset(18, 18, 8, 8);
            footRow.childControlWidth = footRow.childControlHeight = true;
            footRow.childForceExpandWidth = footRow.childForceExpandHeight = false;
            var footFit = footBg.gameObject.AddComponent<ContentSizeFitter>();
            footFit.horizontalFit = footFit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            var foot = UIKit.Text(footBg, SkyfoldInfo.Credit + "   ·   " + SkyfoldInfo.ProjectLabel + "   ·   v" + Application.version, UIStyle.SmallSize, UIStyle.Pearl, false, TextAlignmentOptions.Center, "Footer Text");
            foot.textWrappingMode = TextWrappingModes.NoWrap;
        }

        void PlaceVR()
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null || rigs.Head == null) return;
            var head = rigs.Head;
            Vector3 fwd = rigs.Forward;
            Vector3 pos = head.position + fwd * 1.45f + Vector3.up * -0.08f;
            var rt = (RectTransform)m_VR.transform;
            rt.position = pos;
            rt.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            // Panel content hangs from the top edge; lift so its centre sits near eye level.
            rt.position += Vector3.up * (rt.sizeDelta.y * rt.localScale.y * 0.32f);
            m_VR.worldCamera = rigs.ActiveCamera;
        }

        /// <summary>Re-centres the VR panel in front of the player (pause/recenter).</summary>
        public void RecenterVR()
        {
            if (VRMode && m_Screen != null) PlaceVR();
        }

        // ------------------------------------------------------------------ builder helper
        sealed class Builder
        {
            readonly RectTransform m_Panel;
            readonly MenuController m_Menu;
            public Builder(RectTransform panel, MenuController menu) { m_Panel = panel; m_Menu = menu; }
            public RectTransform Panel => m_Panel;

            T First<T>(T s) where T : Selectable { if (m_Menu.m_First == null && s.IsInteractable()) m_Menu.m_First = s; return s; }

            public void Heading(string text, Color? color = null)
            {
                // The compact title panel is narrower: a slightly smaller heading keeps questions on one line.
                var t = UIKit.Text(m_Panel, text, m_Menu.m_Compact ? 40f : UIStyle.HeadingSize, color ?? UIStyle.Ink, true);
                UIKit.Layout(t, -1f, 56f);
            }

            public TextMeshProUGUI Para(string text, float size = UIStyle.BodySize, Color? color = null)
            {
                var t = UIKit.Text(m_Panel, text, size, color ?? UIStyle.InkSoft);
                return t;
            }

            public Button Button(string label, Action a, bool primary = false, string detail = null, bool enabled = true)
            {
                var btn = UIKit.Button(m_Panel, label, a, primary, m_Menu.m_Compact ? 52f : UIStyle.ButtonHeight, detail);
                btn.interactable = enabled;
                return First(btn);
            }

            public Toggle Toggle(string label, bool v, Action<bool> a) => First(UIKit.Toggle(m_Panel, label, v, a));
            public Slider Slider(string label, float v, Action<float> a, float min = 0f, float max = 1f, Func<float, string> fmt = null, bool whole = false) => First(UIKit.Slider(m_Panel, label, v, a, min, max, fmt, whole));
            public ChoiceSelectable Choice(string label, string[] options, int index, Action<int> a) => First(UIKit.Choice(m_Panel, label, options, index, a));
            public void Space(float h) => UIKit.Spacer(m_Panel, h);
        }

        GameRoot Root => GameRoot.Instance;

        // ------------------------------------------------------------------ screens
        void BuildLauncher(Builder b)
        {
            b.Heading("How do you want to play?");
            b.Para("Both ways play the full game. You can switch from the main menu later.", UIStyle.SmallSize + 2f);
            b.Space(6f);
            b.Button("Play on this laptop", () => Root.ChooseDesktop(), true, "Keyboard + mouse");
            b.Button("Enter VR", () => Root.EnterVR(), false, "Quest 3 via Link");
            b.Space(6f);
            b.Button("Quit", () => Show("quit"));
        }

        void BuildTitle(Builder b, bool vr)
        {
            if (vr)
            {
                b.Heading(SkyfoldInfo.Title, UIStyle.Teal);
                b.Para(SkyfoldInfo.Subtitle, UIStyle.BodySize, UIStyle.Gold);
            }
            var campaign = ProgressStore.Campaign;
            int next = NextEpisode(campaign);
            bool started = campaign.episodes.Any(e => e.completed);
            if (started)
            {
                var def = MissionCatalog.Get(MissionCatalog.ForEpisode(next));
                b.Button("Continue", () => Root.StartMission(def.Id), true, $"Episode {def.Episode}");
            }
            b.Button(started ? "Choose episode" : "Play campaign", () => Show("episodes"), !started, started ? null : "Episode 1");
            b.Button("Three-minute demo", () => Root.StartMission(MissionCatalog.Demo), false, "3 min");
            b.Button("Tutorial", () => Root.StartTutorial(), false, "Replay with guidance");
            if (vr) b.Button("Play on the laptop instead", () => Root.ExitVR());
            else b.Button("Enter VR", () => Root.EnterVR(), false, "Quest 3 via Link");
            b.Button("Controls", () => Show("controls"));
            b.Button("Comfort", () => Show("comfort"));
            b.Button("Audio & subtitles", () => Show("audio"));
            if (!vr) b.Button("Display & mouse", () => Show("display"));
            b.Button("Credits", () => Show("credits"));
            b.Button("Quit", () => Show("quit"));
        }

        static int NextEpisode(CampaignProgress p)
        {
            for (int e = 1; e <= 3; e++)
            {
                var r = p.Record(MissionCatalog.ForEpisode(e));
                if (!r.completed) return Mathf.Min(e, p.unlockedEpisode);
            }
            return 3;
        }

        void BuildEpisodes(Builder b)
        {
            b.Heading("Campaign");
            var p = ProgressStore.Campaign;
            for (int e = 1; e <= 3; e++)
            {
                var def = MissionCatalog.Get(MissionCatalog.ForEpisode(e));
                var rec = p.Record(def.Id);
                bool unlocked = e <= p.unlockedEpisode;
                string detail = !unlocked ? "Locked" : rec.completed ? (string.IsNullOrEmpty(rec.bestMedal) ? "Complete" : rec.bestMedal + " medal") : "New";
                string id = def.Id;
                b.Button($"{e}. {def.Title}", () => Root.StartMission(id), false, detail, unlocked);
            }
            b.Para("Each episode builds on the roads you repaired before. Medals come from storm time left, careful placements, hints and retries.", UIStyle.SmallSize);
            b.Button("Back", Back);
        }

        void BuildControls(Builder b)
        {
            b.Heading("Controls");
            var row = UIKit.Row(b.Panel, "Columns", 28f);
            var left = UIKit.Rect(row, "Desktop");
            var right = UIKit.Rect(row, "VR");
            foreach (var col in new[] { left, right })
            {
                var v = col.gameObject.AddComponent<VerticalLayoutGroup>();
                v.spacing = 6f;
                v.childControlHeight = true;
                v.childControlWidth = true;
                v.childForceExpandHeight = false;
            }
            void Line(RectTransform col, string text, bool head = false)
            {
                // Keep each "key  action" pair on one line; wrap only between pairs.
                var lines = text.Split('\n');
                for (int i = 0; i < lines.Length; i++)
                {
                    var parts = lines[i].Split(new[] { "    ·    " }, System.StringSplitOptions.None);
                    for (int k = 0; k < parts.Length; k++) parts[k] = "<nobr>" + parts[k] + "</nobr>";
                    lines[i] = string.Join("    ·    ", parts);
                }
                text = string.Join("\n", lines);
                var t = UIKit.Text(col, text, head ? UIStyle.BodySize : UIStyle.SmallSize, head ? UIStyle.Teal : UIStyle.Ink, head);
                if (head) t.fontStyle = FontStyles.Bold;
            }
            Line(left, "Laptop: on foot", true);
            Line(left, "W A S D  move    ·    Mouse  look\nE  use / pick up    ·    Q  fold (at a Fold Station)\nTab  objectives    ·    Esc  pause    ·    Shift  walk slowly");
            Line(left, "Laptop: at the plinth", true);
            Line(left, "Hold left mouse  pick up and drag a piece\nR  turn the held piece    ·    release  set it down\nRight-drag or W A S D  orbit    ·    Wheel  zoom\nQ  fold down into the street");
            Line(left, "Laptop: in the car", true);
            Line(left, "W  accelerate    ·    S  brake, hold to reverse\nA / D  steer    ·    Space  parking brake\nE  climb out when stopped    ·    H  horn    ·    C  camera\nHold R  put the car back on the road");
            Line(right, "Quest 3: on foot and at the plinth", true);
            Line(right, "Left stick  move (smooth mode)\nRight stick  turn (snap by default)\nHold A  aim teleport, release to jump\nGrip  grab    ·    Trigger  use / press UI\nX  fold (at a Fold Station)    ·    Y  wrist objectives\nB  back    ·    Left menu button  pause");
            Line(right, "Quest 3: in the car", true);
            Line(right, "Left stick  steer\nRight trigger  accelerate\nLeft trigger  brake, hold at a stop to reverse\nB  climb out when stopped    ·    A  horn\nHold X  put the car back on the road\nY  objectives    ·    Menu  pause");
            Line(right, "The Meta button stays reserved for the headset.", false);
            b.Space(4f);
            b.Toggle("Show input diagnostics panel", SettingsStore.Current.showDiagnostics, v => { SettingsStore.Current.showDiagnostics = v; SettingsStore.Save(); });
            b.Button("Back", Back);
        }

        void BuildComfort(Builder b, bool vr)
        {
            var s = SettingsStore.Current;
            b.Heading("Comfort");
            b.Choice("Movement", new[] { "Smooth (left stick)", "Teleport only (A)" }, (int)s.moveMode, i => { s.moveMode = (MoveMode)i; Apply(); });
            b.Choice("Turning", new[] { "Snap turns", "Smooth turning" }, (int)s.turnMode, i => { s.turnMode = (TurnMode)i; Apply(); });
            int[] angles = { 30, 45, 60, 90 };
            b.Choice("Snap angle", angles.Select(a => a + "°").ToArray(), Array.IndexOf(angles, s.snapAngle) < 0 ? 1 : Array.IndexOf(angles, s.snapAngle), i => { s.snapAngle = angles[i]; Apply(); });
            b.Slider("Smooth turn speed", s.smoothTurnSpeed, v => { s.smoothTurnSpeed = v; Apply(); }, 30f, 150f, v => Mathf.RoundToInt(v) + "°/s");
            b.Slider("Walking speed", s.moveSpeed, v => { s.moveSpeed = v; Apply(); }, 1f, 3.5f, v => v.ToString("0.0") + " m/s");
            b.Toggle("Comfort vignette", s.vignette, v => { s.vignette = v; Apply(); });
            b.Slider("Vignette strength", s.vignetteStrength, v => { s.vignetteStrength = v; Apply(); });
            b.Toggle("Seated play (raises your view)", s.seated, v => { s.seated = v; Apply(); });
            if (vr)
            {
                b.Button("Set my height (stand or sit naturally)", () => { Root.CalibrateHeight(); Refresh(); });
                b.Button("Recenter view", () => Root.Recenter());
            }
            b.Choice("Driving", new[] { "Sit in the car", "Remote, from an overlook" }, (int)s.driveComfort, i => { s.driveComfort = (DriveComfort)i; Apply(); });
            b.Choice("Guidance", new[] { "Full tutorial", "Hints only", "Off" }, (int)s.guidance, i => { s.guidance = (Guidance)i; Apply(); });
            b.Toggle("Reduce flashing", s.reduceFlashing, v => { s.reduceFlashing = v; Apply(); });
            b.Button("Back", Back);
        }

        void BuildAudio(Builder b)
        {
            var s = SettingsStore.Current;
            b.Heading("Audio & subtitles");
            b.Slider("Master", s.master, v => { s.master = v; Apply(); });
            b.Slider("Music", s.music, v => { s.music = v; Apply(); });
            b.Slider("Effects", s.effects, v => { s.effects = v; Apply(); });
            b.Slider("Voice", s.voice, v => { s.voice = v; Apply(); });
            b.Slider("Ambience", s.ambience, v => { s.ambience = v; Apply(); });
            b.Toggle("Subtitles", s.subtitles, v => { s.subtitles = v; Apply(); });
            float[] sizes = { 0.85f, 1f, 1.25f, 1.5f };
            int idx = 1;
            for (int i = 0; i < sizes.Length; i++) if (Mathf.Abs(sizes[i] - s.subtitleScale) < 0.05f) idx = i;
            b.Choice("Subtitle size", new[] { "Small", "Medium", "Large", "Extra large" }, idx, i => { s.subtitleScale = sizes[i]; Apply(); });
            b.Button("Back", Back);
        }

        void BuildDisplay(Builder b)
        {
            var s = SettingsStore.Current;
            b.Heading("Display & mouse");
            b.Choice("Window", new[] { "Fullscreen", "Windowed" }, s.fullscreen ? 0 : 1, i => { s.fullscreen = i == 0; Root.ApplyDisplay(); Apply(); });
            var res = DisplayResolutions();
            int cur = Mathf.Clamp(s.resolutionIndex < 0 ? res.Count - 1 : s.resolutionIndex, 0, res.Count - 1);
            b.Choice("Resolution", res.Select(r => r.x + " × " + r.y).ToArray(), cur, i => { s.resolutionIndex = i; Root.ApplyDisplay(); Apply(); });
            b.Slider("Mouse sensitivity", s.mouseSensitivity, v => { s.mouseSensitivity = v; Apply(); }, 0.2f, 4f, v => v.ToString("0.0") + "×");
            b.Toggle("Invert mouse Y", s.invertY, v => { s.invertY = v; Apply(); });
            b.Slider("Field of view", s.fov, v => { s.fov = v; Apply(); }, 55f, 95f, v => Mathf.RoundToInt(v) + "°", true);
            b.Button("Back", Back);
        }

        public static List<Vector2Int> DisplayResolutions()
        {
            var list = new List<Vector2Int>();
            foreach (var r in UnityEngine.Screen.resolutions)
            {
                var v = new Vector2Int(r.width, r.height);
                if (v.x >= 1280 && !list.Contains(v)) list.Add(v);
            }
            if (list.Count == 0) list.Add(new Vector2Int(UnityEngine.Screen.width, UnityEngine.Screen.height));
            return list;
        }

        void BuildCredits(Builder b)
        {
            b.Heading("Credits");
            b.Para("<b>SKYFOLD: The Last Flight</b>\nCreated by " + SkyfoldInfo.Credit + ". " + SkyfoldInfo.ProjectLabel, UIStyle.BodySize, UIStyle.Ink);
            b.Para(CreditsText.Body, UIStyle.SmallSize);
            b.Button("Back", Back);
        }

        void BuildQuit(Builder b)
        {
            b.Heading("Quit SKYFOLD?");
            b.Para("Your settings and campaign progress are saved.");
            b.Button("Keep playing", Back, true);
            b.Button("Quit to Windows", () => Root.Quit());
        }

        void BuildPause(Builder b, bool vr)
        {
            var md = MissionDirector.Instance;
            b.Heading("Paused");
            if (md != null && md.Current != null)
            {
                var o = md.CurrentObjective;
                b.Para((md.Current.IsDemo ? "Demo" : "Episode " + md.Current.Episode) + " · " + md.Current.Title + (o != null ? "\nNow: " + o.CardText(PlayerRigs.Instance.Mode) : ""), UIStyle.SmallSize + 2f);
            }
            b.Button("Resume", () => Root.Resume(), true);
            if (md?.CurrentObjective?.Hints != null && md.CurrentObjective.Hints.Length > 0)
                b.Button("Show me a hint", () => { md.RequestHint(); Root.Resume(); });
            b.Button("Retry from checkpoint", () => { Root.Resume(); md.Retry(); });
            b.Button("Restart this " + (md != null && md.Current != null && md.Current.IsDemo ? "demo" : "episode"), () => { Root.Resume(); md.Restart(); });
            bool tutorialOn = SettingsStore.Current.guidance == Guidance.FullTutorial;
            b.Button(tutorialOn ? "Skip tutorial lines" : "Turn tutorial back on", () => { SettingsStore.Current.guidance = tutorialOn ? Guidance.HintsOnly : Guidance.FullTutorial; SettingsStore.Save(); Refresh(); });
            if (vr) b.Button("Recenter view", () => { Root.Recenter(); RecenterVR(); });
            b.Button("Comfort", () => Show("comfort"));
            b.Button("Audio & subtitles", () => Show("audio"));
            b.Button("Controls", () => Show("controls"));
            if (md != null && md.Current != null && md.Current.IsDemo) b.Button("Operator: reset demo (keeps campaign)", () => Root.OperatorResetDemo());
            b.Button("Main menu", () => Root.QuitToMenu());
        }

        void BuildFailed(Builder b)
        {
            b.Heading("The storm reached Nacre Bay", UIStyle.Coral);
            b.Para("That happens to every courier. Your repairs are still standing, and the last checkpoint is waiting.");
            b.Button("Try again from the checkpoint", () => MissionDirector.Instance.Retry(), true);
            b.Button("Restart from the beginning", () => MissionDirector.Instance.Restart());
            b.Button("Main menu", () => Root.QuitToMenu());
        }

        void BuildResults(Builder b)
        {
            var md = MissionDirector.Instance;
            var r = md != null ? md.LastResult : null;
            var def = md != null ? md.Current : null;
            if (r == null || def == null) { b.Button("Main menu", () => Root.QuitToMenu(), true); return; }
            b.Heading(def.IsDemo ? "Demo complete" : (def.Episode == 3 ? "The last flight is away" : "Episode complete"), UIStyle.Teal);
            b.Para(def.IsDemo ? "Nacre Bay held. Thank you for playing the demo." : def.Title + (def.Episode == 3 ? ". The city is safe, and it is the one you built." : "."), UIStyle.BodySize, UIStyle.Ink);

            if (!def.IsDemo && !string.IsNullOrEmpty(r.Medal))
            {
                var medalRow = UIKit.Row(b.Panel, "Medal", 18f);
                medalRow.GetComponent<HorizontalLayoutGroup>().childForceExpandWidth = false;
                var disc = UIKit.Image(medalRow, "Disc", UIStyle.Hex(UIStyle.MedalColor(r.Medal)), UIKit.Circle, false);
                disc.preserveAspect = true;
                UIKit.Layout(disc, 84f, 84f, 0f, 84f);
                // A pearl ring inside the disc so it reads as a medal, not a dot.
                var ring = UIKit.Image(disc.rectTransform, "Ring", new Color(1f, 1f, 1f, 0.55f), UIKit.Ring, false);
                ring.preserveAspect = true;
                ring.rectTransform.anchorMin = new Vector2(0.18f, 0.18f);
                ring.rectTransform.anchorMax = new Vector2(0.82f, 0.82f);
                ring.rectTransform.offsetMin = ring.rectTransform.offsetMax = Vector2.zero;
                var mt = UIKit.Text(medalRow, r.Medal + " medal", UIStyle.HeadingSize, UIStyle.Ink, true);
                UIKit.Layout(mt, 84f, -1f, 1f);
            }
            int mm = Mathf.FloorToInt(r.TimeLeft / 60f), ss = Mathf.FloorToInt(r.TimeLeft % 60f);
            b.Para($"Storm time left: <b>{mm}:{ss:00}</b> of {Mathf.RoundToInt(r.StormSeconds / 60f)} min\n" +
                   $"Pieces placed: {r.PlacementAttempts - r.Rejected}   ·   rejected tries: {r.Rejected}\n" +
                   $"Hints shown: {r.HintsShown}   ·   retries: {r.Retries}" +
                   (def.Episode == 1 ? $"\nRoute: {(r.UsedShortcut ? "the east shortcut" : "the west causeway")} ({r.RouteLength} blocks)" : "") +
                   $"\nScore: {r.Score}", UIStyle.SmallSize + 2f, UIStyle.Ink);
            if (!string.IsNullOrEmpty(def.MedalRulesText)) b.Para(def.MedalRulesText, UIStyle.SmallSize - 2f);
            foreach (var n in r.Notes) b.Para(n, UIStyle.SmallSize);

            if (!def.IsDemo && def.Episode < 3)
            {
                string next = MissionCatalog.ForEpisode(def.Episode + 1);
                b.Button("Next: " + MissionCatalog.Get(next).Title, () => Root.StartMission(next), true);
            }
            b.Button(def.IsDemo ? "Play the demo again" : "Replay this episode", () => Root.StartMission(def.Id), def.IsDemo || def.Episode == 3);
            if (def.Episode == 3) b.Button("Credits", () => { Root.QuitToMenu(); Show("credits"); });
            b.Button("Main menu", () => Root.QuitToMenu());
        }

        void BuildVRStart(Builder b)
        {
            b.Heading("Starting VR…");
            b.Para("1. Connect the Quest 3 with a USB-C cable (or turn on Air Link).\n2. In the headset: Quick Settings, then Link, then choose this PC.\n3. Wait for the Link home screen, then look for SKYFOLD.", UIStyle.SmallSize + 2f, UIStyle.Ink);
            b.Para("SKYFOLD cannot press those headset buttons for you.", UIStyle.SmallSize);
            b.Button("Play on this laptop instead", () => Root.CancelVR());
        }

        void BuildVRFail(Builder b)
        {
            var xr = XRBootstrap.Instance;
            b.Heading("VR did not start", UIStyle.Coral);
            b.Para(xr != null ? xr.LastError : "Unknown error.", UIStyle.BodySize, UIStyle.Ink);
            b.Para("Checklist: Meta Horizon Link app open on this PC · headset connected (cable or Air Link) · Link enabled in the headset · Meta set as the active OpenXR runtime.\nLog file: " + Application.consoleLogPath, UIStyle.SmallSize);
            b.Button("Retry", () => Root.EnterVR(), true);
            b.Button("Play on this laptop", () => Root.ChooseDesktop());
            b.Para("If Retry keeps failing, close SKYFOLD and start it with the \"SKYFOLD - Quest 3\" shortcut once Link is running. Your progress is kept.", UIStyle.SmallSize);
        }

        void BuildFirstComfort(Builder b)
        {
            var s = SettingsStore.Current;
            b.Heading("Choose how you move");
            b.Para("You can change this any time under Comfort.", UIStyle.SmallSize);
            void Pick(MoveMode m, TurnMode t)
            {
                s.moveMode = m; s.turnMode = t; s.comfortChosen = true; Apply();
                Show("title", false);
            }
            b.Button("Teleport + snap turns", () => Pick(MoveMode.TeleportOnly, TurnMode.Snap), true, "Most comfortable");
            b.Button("Smooth movement + snap turns", () => Pick(MoveMode.Smooth, TurnMode.Snap), false, "Balanced");
            b.Button("Smooth movement + smooth turns", () => Pick(MoveMode.Smooth, TurnMode.Smooth), false, "Experienced");
            b.Toggle("I'm playing seated", s.seated, v => { s.seated = v; Apply(); });
        }

        void Apply()
        {
            SettingsStore.Save();
            Root.ApplySettings();
        }
    }
}
