using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Bootstrap and top-level flow: launch arguments, settings, the single CityState shared by every
    /// system, launcher/title/play/pause/results, and the desktop-first Enter VR / Exit VR lifecycle.
    /// </summary>
    public sealed class GameRoot : MonoBehaviour
    {
        public static GameRoot Instance { get; private set; }

        [Header("Systems")]
        public PlayerRigs rigs;
        public InputRouter input;
        public XRBootstrap xr;
        public MissionDirector missions;
        public DialogueDirector dialogue;
        public AudioDirector audioDirector;
        public FoldController fold;
        public TabletopController tabletop;
        public CourierVehicle car;
        public PowerCell cell;
        public BeaconSystem beacons;
        public ConvoyDirector convoy;
        public AircraftSequence aircraft;
        public NuriCompanion nuri;
        public RouteGuide guide;
        public Substation substation;
        public TrafficDirector traffic;
        public List<FullScaleSlot> slots = new List<FullScaleSlot>();
        public MenuController menu;
        public HUDController hud;
        public ScreenFader fader;
        public InputDiagnostics diagnostics;
        public QARunner qa;

        public CityState City { get; private set; }
        public CityLayout Layout { get; private set; }
        public bool IsPlaying { get; private set; }
        public bool IsPaused { get; private set; }
        public PlayMode Mode => rigs != null ? rigs.Mode : PlayMode.Desktop;

        InputContext m_ContextBeforePause;
        bool m_VRStarting;
        bool m_PendingDemo;
        Coroutine m_VRRoutine;
        Transform m_DynamicProxy;

        void Awake()
        {
            Instance = this;
            var opts = LaunchOptions.Init();
            SettingsStore.Load();
            ProgressStore.Load();
            if (opts.Windowed) SettingsStore.Current.fullscreen = false;
            QualitySettings.vSyncCount = 1;
            Application.targetFrameRate = -1;

            Layout = CityLayout.NacreBay;
            City = new CityState(Layout);
            City.OccupancyCheck = Occupancy;
            foreach (var s in slots) if (s != null) s.Bind(City);
            tabletop.Bind(City);
            beacons.Bind(City);
            convoy.Bind(City);
            aircraft.Bind(City, Layout);
            substation.Bind(City);
            guide.Bind(City);
            traffic.Bind(City);

            missions.Ctx = new MissionContext
            {
                City = City, Layout = Layout, Tabletop = tabletop, Fold = fold, Rigs = rigs, Car = car, Cell = cell,
                Beacons = beacons, Convoy = convoy, Aircraft = aircraft, Dialogue = dialogue, Nuri = nuri, Guide = guide,
                Director = missions, Substation = substation
            };
            m_DynamicProxy = new GameObject("Dynamic Target Proxy").transform;
            m_DynamicProxy.SetParent(transform, false);
            RegisterDynamicTargets();
            m_PendingDemo = opts.Demo;
            LogSystem(opts);
            ApplyDisplay();
        }

        void Start()
        {
            rigs.SetMode(PlayMode.Desktop);
            input.SetMode(PlayMode.Desktop);
            dialogue.Mode = PlayMode.Desktop;
            fader.AttachTo(rigs.desktop.cam);
            if (rigs.vr != null && rigs.vr.origin != null && rigs.vr.origin.Camera != null) fader.AttachTo(rigs.vr.origin.Camera);
            ApplySettings();
            missions.PrepareShowcase();
            EnterTitleState();

            var o = LaunchOptions.Current;
            if (!string.IsNullOrEmpty(o.QaScenario) && qa != null)
            {
                qa.Run(o.QaScenario, o.QaOut);
                return;
            }
            if (o.Mode == LaunchMode.VR) EnterVR();
            else if (o.Mode == LaunchMode.Desktop) ChooseDesktop();
            else menu.Show("launcher", false);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        // ------------------------------------------------------------------ flow
        public void ChooseDesktop()
        {
            if (m_VRRoutine != null) { StopCoroutine(m_VRRoutine); m_VRRoutine = null; m_VRStarting = false; }
            if (xr.State == XRState.Running || xr.State == XRState.Starting) xr.StopXR();
            SwitchRig(PlayMode.Desktop);
            EnterTitleState();
            if (m_PendingDemo) { m_PendingDemo = false; StartMission(MissionCatalog.Demo); return; }
            menu.Show("title", false);
        }

        void EnterTitleState()
        {
            IsPlaying = false;
            IsPaused = false;
            Time.timeScale = 1f;
            input.SetContext(InputContext.Menu);
            var a = Layout.GetAnchor("atelier.player");
            rigs.TeleportTo(a);
            if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(InputContext.Menu);
            else
            {
                rigs.desktop.SetView(DesktopView.Title);
                rigs.desktop.UpdateCursor();
            }
            audioDirector.SetMusic("music_menu_loop", 2.5f);
            audioDirector.SetAmbience("amb_atelier_loop");
            nuri.SnapToPlayer();
        }

        public void StartMission(string id)
        {
            var def = MissionCatalog.Get(id);
            menu.Close();
            IsPaused = false;
            Time.timeScale = 1f;
            audioDirector.SetPaused(false);
            dialogue.SetPaused(false);
            IsPlaying = true;
            missions.Begin(def);
        }

        public void StartTutorial()
        {
            SettingsStore.Current.guidance = Guidance.FullTutorial;
            SettingsStore.Save();
            StartMission(MissionCatalog.Episode1);
        }

        public void Pause()
        {
            if (!IsPlaying || IsPaused) return;
            IsPaused = true;
            m_ContextBeforePause = input.Context;
            tabletop.ForceDrop();
            Time.timeScale = 0f;
            input.SetContext(InputContext.Paused);
            if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(InputContext.Paused);
            else rigs.desktop.UpdateCursor();
            audioDirector.SetPaused(true);
            dialogue.SetPaused(true);
            menu.Show("pause", false);
        }

        public void Resume()
        {
            if (!IsPaused) return;
            IsPaused = false;
            Time.timeScale = 1f;
            menu.Close();
            audioDirector.SetPaused(false);
            dialogue.SetPaused(false);
            input.SetContext(m_ContextBeforePause == InputContext.Paused ? InputContext.OnFoot : m_ContextBeforePause);
            if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(input.Context);
            else rigs.desktop.UpdateCursor();
        }

        public void QuitToMenu()
        {
            missions.Abort();
            IsPaused = false;
            Time.timeScale = 1f;
            audioDirector.SetPaused(false);
            dialogue.SetPaused(false);
            missions.PrepareShowcase();
            EnterTitleState();
            menu.Show("title", false);
        }

        public void OperatorResetDemo()
        {
            ProgressStore.ResetDemo();
            Debug.Log("[SKYFOLD] Operator reset: demo restarted, campaign progress untouched.");
            StartMission(MissionCatalog.Demo);
        }

        public void Quit()
        {
            SettingsStore.Save();
            if (xr.State == XRState.Running) xr.StopXR();
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        // ------------------------------------------------------------------ VR lifecycle
        public void EnterVR()
        {
            if (m_VRStarting) return;
            m_VRRoutine = StartCoroutine(EnterVRRoutine());
        }

        IEnumerator EnterVRRoutine()
        {
            m_VRStarting = true;
            menu.Show("vrstart", false);
            yield return xr.StartXR();
            m_VRStarting = false;
            m_VRRoutine = null;
            if (xr.State != XRState.Running)
            {
                menu.Show("vrfail", false);
                yield break;
            }
            SwitchRig(PlayMode.VR);
            EnterTitleState();
            yield return null;
            if (m_PendingDemo) { m_PendingDemo = false; StartMission(MissionCatalog.Demo); yield break; }
            menu.Show(SettingsStore.Current.comfortChosen ? "title" : "firstcomfort", false);
        }

        public void CancelVR() => ChooseDesktop();

        public void ExitVR()
        {
            if (IsPlaying) missions.Abort();
            xr.StopXR();
            SwitchRig(PlayMode.Desktop);
            missions.PrepareShowcase();
            EnterTitleState();
            menu.Show("title", false);
        }

        void SwitchRig(PlayMode mode)
        {
            rigs.SetMode(mode);
            input.SetMode(mode);
            dialogue.Mode = mode;
            if (mode == PlayMode.VR)
            {
                fader.AttachTo(rigs.vr.Camera);
                rigs.vr.ApplyComfort(SettingsStore.Current);
            }
            ApplySettings();
        }

        public void CalibrateHeight()
        {
            if (rigs.Mode != PlayMode.VR || rigs.vr.Camera == null) return;
            var s = SettingsStore.Current;
            float tracked = rigs.vr.Camera.transform.localPosition.y;
            s.seated = false;
            s.heightOffset = Mathf.Clamp(1.62f - tracked, -0.6f, 0.8f);
            SettingsStore.Save();
            HUDMessages.Toast("Height set. Your eyes are now at about 1.62 m.");
        }

        public void Recenter()
        {
            if (rigs.Mode == PlayMode.VR) rigs.vr.Recenter();
        }

        // ------------------------------------------------------------------ settings
        public void ApplySettings()
        {
            var s = SettingsStore.Current;
            if (rigs.vr != null) rigs.vr.ApplyComfort(s);
            if (rigs.desktop != null) rigs.desktop.ApplySettings(s);
        }

        public void ApplyDisplay()
        {
            var s = SettingsStore.Current;
            if (Application.isEditor) return;
            var list = MenuController.DisplayResolutions();
            var res = s.resolutionIndex >= 0 && s.resolutionIndex < list.Count ? list[s.resolutionIndex] : new Vector2Int(Display.main.systemWidth, Display.main.systemHeight);
            if (s.fullscreen) Screen.SetResolution(res.x, res.y, FullScreenMode.FullScreenWindow);
            else
            {
                var w = s.resolutionIndex >= 0 ? res : new Vector2Int(Mathf.Min(1600, Display.main.systemWidth - 80), Mathf.Min(900, Display.main.systemHeight - 120));
                Screen.SetResolution(w.x, w.y, FullScreenMode.Windowed);
            }
        }

        // ------------------------------------------------------------------ per frame
        void Update()
        {
            if (input.Pause.WasPressedThisFrame())
            {
                if (IsPlaying && !IsPaused && missions.State == MissionState.Active) Pause();
                else if (IsPaused && menu.Screen == "pause") Resume();
            }
            if (IsPlaying && !IsPaused && input.Objectives.WasPressedThisFrame()) hud.ToggleObjectives();
            if (input.OperatorReset.WasPressedThisFrame() && missions.Current != null && missions.Current.IsDemo) OperatorResetDemo();
            if (input.Screenshot.WasPressedThisFrame()) TakeScreenshot(null);

            // Headset removed or a controller lost while playing: pause safely.
            if (IsPlaying && !IsPaused && rigs.Mode == PlayMode.VR && xr.State == XRState.Running && missions.State == MissionState.Active)
            {
                if (!xr.UserPresent) { Debug.Log("[SKYFOLD] Headset removed: pausing."); Pause(); }
            }

            if (IsPlaying && !IsPaused)
            {
                if (missions.State == MissionState.Failed && menu.Screen != "failed")
                {
                    tabletop.ForceDrop();
                    input.SetContext(InputContext.Results);
                    if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(InputContext.Results); else rigs.desktop.UpdateCursor();
                    menu.Show("failed", false);
                }
                else if (missions.State == MissionState.Results && menu.Screen != "results")
                {
                    input.SetContext(InputContext.Results);
                    if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(InputContext.Results); else rigs.desktop.UpdateCursor();
                    menu.Show("results", false);
                }
                else if (missions.State == MissionState.Active && (menu.Screen == "failed" || menu.Screen == "results")) menu.Close();
            }
        }

        void OnApplicationFocus(bool focus)
        {
            if (!focus && IsPlaying && !IsPaused && rigs != null && rigs.Mode == PlayMode.Desktop && (qa == null || !qa.Running))
                Pause();
        }

        void OnApplicationQuit()
        {
            SettingsStore.Save();
        }

        public string TakeScreenshot(string name)
        {
            string dir = Path.Combine(Application.persistentDataPath, "Screenshots");
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, (name ?? "skyfold_" + System.DateTime.Now.ToString("yyyyMMdd_HHmmss")) + ".png");
            ScreenCapture.CaptureScreenshot(path);
            Debug.Log("[SKYFOLD] Screenshot: " + path);
            return path;
        }

        // ------------------------------------------------------------------ helpers
        bool Occupancy(string socketId, out string reason)
        {
            reason = null;
            var s = Layout.Socket(socketId);
            if (s == null) return true;
            if (car != null && car.Cell == s.Cell) { reason = "The courier car is parked on that piece."; return false; }
            foreach (var v in convoy.shuttles)
                if (v != null && v.Cell == s.Cell) { reason = "The convoy is crossing it. Wait a moment."; return false; }
            foreach (var v in traffic.cars)
                if (v != null && v.gameObject.activeInHierarchy && v.Cell == s.Cell) { reason = "A car is crossing it. Wait a moment."; return false; }
            return true;
        }

        void RegisterDynamicTargets()
        {
            SceneRegistry.RegisterDynamic("socket.nearest", () =>
            {
                var mini = MiniCity.Instance;
                if (mini == null) return null;
                TileSocket best = null;
                float bestD = float.MaxValue;
                Vector3 head = rigs.Head != null ? rigs.Head.position : Vector3.zero;
                foreach (var s in mini.Sockets)
                {
                    if (!City.IsActive(s.socketId) || !City.GetPlacement(s.socketId).IsEmpty) continue;
                    float d = (s.transform.position - head).sqrMagnitude;
                    if (d < bestD) { bestD = d; best = s; }
                }
                return best != null ? best.transform : null;
            });
            SceneRegistry.RegisterDynamic("beacon.next", () => beacons.NextSwitch());
            SceneRegistry.RegisterDynamic("route.island", () =>
            {
                var route = City.FindRoute("depot", "substation");
                if (route == null) return null;
                foreach (var c in route)
                    if (c.y >= 5) { m_DynamicProxy.position = CityLayout.CellCenter(c); return m_DynamicProxy; }
                return null;
            });
        }

        static void LogSystem(LaunchOptions opts)
        {
            Debug.Log($"[SKYFOLD] {SkyfoldInfo.Title} {Application.version} (Unity {Application.unityVersion}) · {SkyfoldInfo.ProjectLabel}");
            Debug.Log($"[SKYFOLD] Launch options: {opts}");
            Debug.Log($"[SKYFOLD] GPU: {SystemInfo.graphicsDeviceName} ({SystemInfo.graphicsDeviceType}, {SystemInfo.graphicsMemorySize} MB) · CPU: {SystemInfo.processorType} ({SystemInfo.processorCount} threads) · RAM {SystemInfo.systemMemorySize} MB · {SystemInfo.operatingSystem}");
            Debug.Log($"[SKYFOLD] Display {Screen.currentResolution.width}x{Screen.currentResolution.height} @ {Screen.currentResolution.refreshRateRatio.value:0} Hz · data: {Application.persistentDataPath} · log: {Application.consoleLogPath}");
        }
    }
}
