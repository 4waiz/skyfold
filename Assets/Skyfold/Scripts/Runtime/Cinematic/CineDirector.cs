using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Debug = UnityEngine.Debug;

namespace Skyfold
{
    /// <summary>
    /// Trailer capture mode, started with --cine=all (or a comma list of shot ids). The real game runs on a
    /// fixed 30 fps clock; only the cameras are scripted. Each shot renders offscreen (supersampled) and is
    /// piped straight into ffmpeg as one MP4. Uses its own save folder and mutes the game's audio. Never part
    /// of normal play.
    ///   --cine=A1,A2      shots to capture (see Order)       --cine-portrait   9:16 framing (default 16:9)
    ///   --cine-out=DIR    where the MP4s go                  --cine-stills     3 JPG stills per shot instead
    ///   --cine-ffmpeg=EXE ffmpeg executable
    /// </summary>
    [DefaultExecutionOrder(10000)]
    public sealed class CineDirector : MonoBehaviour
    {
        static string s_Shots, s_Out, s_Ffmpeg = "ffmpeg";
        static bool s_Portrait, s_Stills;
        const int Fps = 30;

        static readonly string[] Order = { "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5", "B6", "C1", "C2", "C3", "C4", "C5", "C6" };

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            foreach (var a in Environment.GetCommandLineArgs())
            {
                if (a.StartsWith("--cine=", StringComparison.Ordinal)) s_Shots = a.Substring(7);
                else if (a.StartsWith("--cine-out=", StringComparison.Ordinal)) s_Out = a.Substring(11);
                else if (a.StartsWith("--cine-ffmpeg=", StringComparison.Ordinal)) s_Ffmpeg = a.Substring(14);
                else if (a == "--cine-portrait") s_Portrait = true;
                else if (a == "--cine-stills") s_Stills = true;
            }
            if (string.IsNullOrEmpty(s_Shots)) return;
            if (string.IsNullOrEmpty(s_Out)) s_Out = Path.Combine(Application.persistentDataPath, "Cine");
            // Fresh, separate saves: a capture never touches the player's progress.
            string saves = Path.Combine(Application.persistentDataPath, "CINE_saves");
            if (Directory.Exists(saves)) Directory.Delete(saves, true);
            Directory.CreateDirectory(saves);
            JsonFile.Override = saves;
            var go = new GameObject("CineDirector");
            DontDestroyOnLoad(go);
            go.AddComponent<CineDirector>();
        }

        // ------------------------------------------------------------------ state
        Camera m_Cam;
        RenderTexture m_Rt;
        Texture2D m_Tex;
        byte[] m_Buf;
        Process m_Enc;
        Stream m_Pipe;
        int m_W, m_H, m_OutW, m_OutH;
        Volume m_DofVolume;
        DepthOfField m_Dof;
        Action<float> m_CamFn;
        float m_RecStart, m_RecDur;
        float m_Storm = -1f;
        StreamWriter m_Log;
        readonly Dictionary<string, Func<IEnumerator>> m_Shots = new Dictionary<string, Func<IEnumerator>>();
        bool m_Driving;

        static GameRoot Root => GameRoot.Instance;
        static bool P => s_Portrait;
        static float F(float landscape, float portrait) => s_Portrait ? portrait : landscape;

        IEnumerator Start()
        {
            Directory.CreateDirectory(s_Out);
            m_Log = new StreamWriter(Path.Combine(s_Out, $"cine_{(P ? "portrait" : "landscape")}.log"), false);
            Time.captureFramerate = Fps;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            StartCoroutine(Pace());
            AudioListener.volume = 0f;
            Log($"cine start: shots={s_Shots} aspect={(P ? "portrait" : "landscape")} stills={s_Stills} gpu={SystemInfo.graphicsDeviceName}");
            yield return Wait(2f);
            SetupCamera();
            Register();
            var list = s_Shots == "all" ? Order : s_Shots.Split(',');
            foreach (var id in list)
            {
                if (!m_Shots.TryGetValue(id.Trim(), out var shot)) { Log("unknown shot " + id); continue; }
                Log($"shot {id} begin (game t={Time.time:0.0}s, real t={Time.realtimeSinceStartup:0.0}s)");
                yield return StartCoroutine(shot());
                StopDriving();
            }
            Log($"cine done (real t={Time.realtimeSinceStartup:0.0}s)");
            m_Log.Close();
            Application.Quit(0);
        }

        /// <summary>
        /// Holds real time to the 30 fps game clock. Some game effects (piece snaps, switch throws, UI) run on
        /// unscaled real time; pacing the loop keeps them at true speed in the capture.
        /// </summary>
        IEnumerator Pace()
        {
            var eof = new WaitForEndOfFrame();
            double next = Time.realtimeSinceStartupAsDouble;
            while (true)
            {
                yield return eof;
                next += 1.0 / Fps;
                double wait = next - Time.realtimeSinceStartupAsDouble;
                if (wait > 0.018) Thread.Sleep((int)((wait - 0.016) * 1000.0));
                while (Time.realtimeSinceStartupAsDouble < next) { }
                if (Time.realtimeSinceStartupAsDouble - next > 0.25) next = Time.realtimeSinceStartupAsDouble;
            }
        }

        void Log(string line)
        {
            Debug.Log("[CINE] " + line);
            m_Log?.WriteLine(line);
            m_Log?.Flush();
        }

        static IEnumerator Wait(float seconds)
        {
            float end = Time.time + seconds;
            while (Time.time < end) yield return null;
        }

        // ------------------------------------------------------------------ camera + capture
        void SetupCamera()
        {
            var desk = PlayerRigs.Instance.desktop;
            var deskCam = desk.cam;
            m_W = P ? 1440 : 2560; m_H = P ? 2560 : 1440;
            m_OutW = P ? 1080 : 1920; m_OutH = P ? 1920 : 1080;

            var go = new GameObject("Cine Camera");
            m_Cam = go.AddComponent<Camera>();
            m_Cam.CopyFrom(deskCam);
            var data = m_Cam.GetUniversalAdditionalCameraData();
            var deskData = deskCam.GetUniversalAdditionalCameraData();
            data.renderPostProcessing = true;
            data.volumeLayerMask = deskData.volumeLayerMask;
            data.renderShadows = true;
            data.antialiasing = AntialiasingMode.None;
            m_Cam.allowMSAA = true;
            m_Cam.nearClipPlane = 0.05f;
            m_Cam.farClipPlane = 2600f;
            m_Rt = new RenderTexture(m_W, m_H, 24, RenderTextureFormat.ARGB32) { antiAliasing = 1, name = "Cine RT" };
            m_Rt.Create();
            m_Cam.targetTexture = m_Rt;

            // The player's own camera stops rendering; its transform still anchors NURI's flight.
            deskCam.enabled = false;
            desk.enabled = false;
            m_Tex = new Texture2D(m_W, m_H, TextureFormat.RGB24, false);
            m_Buf = new byte[m_W * m_H * 3];

            var vgo = new GameObject("Cine Depth Of Field");
            m_DofVolume = vgo.AddComponent<Volume>();
            m_DofVolume.isGlobal = true;
            m_DofVolume.priority = 100f;
            m_DofVolume.weight = 0f;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            m_Dof = profile.Add<DepthOfField>(true);
            m_Dof.mode.Override(DepthOfFieldMode.Bokeh);
            m_Dof.focusDistance.Override(1f);
            m_Dof.aperture.Override(2.8f);
            m_Dof.focalLength.Override(50f);
            m_DofVolume.sharedProfile = profile;
            Log($"camera ready {m_W}x{m_H} -> {m_OutW}x{m_OutH}");
        }

        void Dof(float focus, float aperture = 2.8f, float focal = 50f, float weight = 1f)
        {
            m_Dof.focusDistance.Override(Mathf.Max(0.01f, focus));
            m_Dof.aperture.Override(aperture);
            m_Dof.focalLength.Override(focal);
            m_DofVolume.weight = weight;
        }

        void NoDof() => m_DofVolume.weight = 0f;

        void Pose(Vector3 pos, Vector3 lookAt, float fov, float near = 0.05f)
        {
            m_Cam.transform.position = pos;
            Vector3 d = lookAt - pos;
            if (d.sqrMagnitude > 1e-8f) m_Cam.transform.rotation = Quaternion.LookRotation(d.normalized, Vector3.up);
            m_Cam.fieldOfView = fov;
            m_Cam.nearClipPlane = near;
        }

        void LateUpdate()
        {
            if (m_Storm >= 0f && StormDirector.Instance != null) StormDirector.Instance.SetProgress(m_Storm);
            if (RouteGuide.Instance != null) RouteGuide.Instance.Hide();
            if (m_CamFn != null) m_CamFn(m_RecDur > 0f ? Mathf.Clamp01((Time.time - m_RecStart) / m_RecDur) : 0f);
        }

        /// <summary>Records one shot: the camera function runs every frame with t from 0 to 1.</summary>
        IEnumerator Record(string id, float landscapeSeconds, float portraitSeconds, Action<float> cam)
        {
            float seconds = F(landscapeSeconds, portraitSeconds);
            int frames = Mathf.Max(2, Mathf.RoundToInt(seconds * Fps));
            m_RecStart = Time.time;
            m_RecDur = (frames - 1) / (float)Fps;
            m_CamFn = cam;
            string file = Path.Combine(s_Out, $"{id}_{(P ? "portrait" : "landscape")}");
            if (!s_Stills) StartEncoder(file + ".mp4");
            float real0 = Time.realtimeSinceStartup;
            for (int f = 0; f < frames; f++)
            {
                yield return new WaitForEndOfFrame();
                if (s_Stills)
                {
                    if (f == 0 || f == frames / 2 || f == frames - 1) SaveStill($"{file}_{f:000}.jpg");
                }
                else Grab();
            }
            if (!s_Stills) StopEncoder();
            m_CamFn = null;
            Log($"shot {id}: {frames} frames ({seconds:0.0}s) captured in {Time.realtimeSinceStartup - real0:0.0}s real time");
        }

        void ReadFrame()
        {
            var prev = RenderTexture.active;
            RenderTexture.active = m_Rt;
            m_Tex.ReadPixels(new Rect(0, 0, m_W, m_H), 0, 0, false);
            RenderTexture.active = prev;
        }

        void Grab()
        {
            ReadFrame();
            m_Tex.GetRawTextureData<byte>().CopyTo(m_Buf);
            try { m_Pipe.Write(m_Buf, 0, m_Buf.Length); }
            catch (Exception e) { Log("encoder write failed: " + e.Message); }
        }

        void SaveStill(string path)
        {
            ReadFrame();
            m_Tex.Apply(false);
            File.WriteAllBytes(path, m_Tex.EncodeToJPG(90));
        }

        void StartEncoder(string path)
        {
            string args = $"-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {m_W}x{m_H} -r {Fps} -i - " +
                          $"-vf vflip,scale={m_OutW}:{m_OutH}:flags=lanczos -c:v libx264 -preset medium -crf 15 -pix_fmt yuv420p -movflags +faststart \"{path}\"";
            var psi = new ProcessStartInfo(s_Ffmpeg, args) { UseShellExecute = false, RedirectStandardInput = true, CreateNoWindow = true };
            m_Enc = Process.Start(psi);
            m_Pipe = m_Enc.StandardInput.BaseStream;
        }

        void StopEncoder()
        {
            try
            {
                m_Pipe.Flush();
                m_Pipe.Close();
                if (!m_Enc.WaitForExit(120000)) Log("encoder did not exit in time");
                else if (m_Enc.ExitCode != 0) Log("encoder exit code " + m_Enc.ExitCode);
            }
            catch (Exception e) { Log("encoder close failed: " + e.Message); }
            m_Enc.Dispose();
            m_Enc = null;
            m_Pipe = null;
        }

        // ------------------------------------------------------------------ world helpers
        IEnumerator Fresh(bool street, float storm = 0.08f)
        {
            StopDriving();
            Root.StartMission(MissionCatalog.Demo);
            yield return Wait(0.7f);
            foreach (var tm in FindObjectsByType<TargetMarker>(FindObjectsInactive.Include)) tm.gameObject.SetActive(false);
            if (street)
            {
                var fold = FoldController.Instance;
                fold.SetLocationImmediate(false, fold.Station("kiosk.A"), new Anchor(new Vector3(129f, 0.15f, 31f), 0f));
                yield return Wait(0.2f);
            }
            m_Storm = storm;
            NoDof();
        }

        static Vector3 Mini(float x, float y, float z) => MiniCity.Instance.transform.TransformPoint(new Vector3(x, y, z));

        static Vector3 Lerp3(Vector3 a, Vector3 b, float t) => Vector3.LerpUnclamped(a, b, t);
        static float Smooth(float t) => t * t * (3f - 2f * t);
        static float InOutCubic(float t) => t < 0.5f ? 4f * t * t * t : 1f - Mathf.Pow(-2f * t + 2f, 3f) * 0.5f;
        static float OutCubic(float t) => 1f - Mathf.Pow(1f - t, 3f);
        static float Range01(float t, float a, float b) => Mathf.Clamp01((t - a) / Mathf.Max(0.0001f, b - a));

        /// <summary>Sets the bridge into the east crossing through the normal release path, with no animation.</summary>
        IEnumerator PlaceBridgeNow()
        {
            var tt = TabletopController.Instance;
            var piece = tt.Piece("piece.bridge");
            var socket = MiniCity.Instance.Socket("bridge_east");
            if (piece == null || socket == null) { Log("bridge piece or socket missing"); yield break; }
            if (!Root.City.GetPlacement("bridge_east").IsEmpty) yield break;
            if (!tt.BeginHold(piece)) { Log("bridge pick-up refused"); yield break; }
            piece.BeginDesktopHold();
            TurnTo(piece, ValidQuarter(piece));
            piece.transform.SetPositionAndRotation(socket.transform.position + Vector3.up * 0.03f, QuarterRotation(piece.CurrentQuarter));
            yield return null;
            ReleaseIntoSocket(piece, socket);
            yield return null;
            Log("bridge placed: " + !Root.City.GetPlacement("bridge_east").IsEmpty);
        }

        /// <summary>Lets go of a desktop-held piece; on success it is set straight down (no snap hop).</summary>
        void ReleaseIntoSocket(ModulePiece piece, TileSocket socket)
        {
            piece.EndDesktopHold();
            TabletopController.Instance.Release(piece);
            if (piece.SocketId == socket.socketId)
                piece.SetImmediate(socket.transform.position, QuarterRotation(piece.CurrentQuarter), PieceState.Placed);
        }

        /// <summary>The first quarter turn (from the tray orientation) that the east crossing accepts.</summary>
        int ValidQuarter(ModulePiece piece)
        {
            int q = piece.CurrentQuarter;
            for (int i = 0; i < 4; i++, q = (q + 1) & 3)
                if (Root.City.Check("bridge_east", piece.type, q).Ok) return q;
            Log("no accepted quarter for the bridge");
            return piece.CurrentQuarter;
        }

        static void TurnTo(ModulePiece piece, int quarter)
        {
            for (int i = 0; i < 4 && piece.CurrentQuarter != (quarter & 3); i++) piece.DesktopRotate();
        }

        static Quaternion QuarterRotation(int q) => MiniCity.Instance.CityToWorldRotation(Quaternion.Euler(0f, q * 90f, 0f));

        /// <summary>Frame-rate-fixed version of the desktop hold follow (the game's own uses real time).</summary>
        static void HoldPiece(ModulePiece piece, Vector3 target, float posRate = 14f, float rotRate = 9f)
        {
            Vector3 p = Vector3.Lerp(piece.transform.position, target, 1f - Mathf.Exp(-posRate / Fps));
            Quaternion r = Quaternion.Slerp(piece.transform.rotation, QuarterRotation(piece.CurrentQuarter), 1f - Mathf.Exp(-rotRate / Fps));
            piece.transform.SetPositionAndRotation(p, r);
        }

        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        /// <summary>Same look as BeaconSystem.SetLens, so a scripted sweep matches the game's lit beacons.</summary>
        void SetBeaconLens(Renderer r, bool on)
        {
            if (r == null) return;
            if (m_Block == null) m_Block = new MaterialPropertyBlock();
            r.GetPropertyBlock(m_Block);
            m_Block.SetColor(EmissionId, on ? new Color(1f, 0.82f, 0.42f) * 6f : new Color(0.05f, 0.05f, 0.05f));
            r.SetPropertyBlock(m_Block);
        }

        static FullScaleSlot Slot(string id)
        {
            foreach (var s in FindObjectsByType<FullScaleSlot>(FindObjectsInactive.Include)) if (s.socketId == id) return s;
            return null;
        }

        void PowerUp()
        {
            var cell = PowerCell.Instance;
            var socket = Substation.Instance != null ? Substation.Instance.socket : null;
            if (cell != null && socket != null) cell.InsertInto(socket);
            Root.City.SetFlag(Flags.SubstationPowered, true);
        }

        // ------------------------------------------------------------------ driving (real keys, like a careful player)
        sealed class Line
        {
            readonly List<Vector3> m_P = new List<Vector3>();
            readonly float[] m_S;
            public float Length => m_S[m_S.Length - 1];
            public Line(List<Vector3> pts)
            {
                foreach (var p in pts)
                {
                    var q = new Vector3(p.x, 0f, p.z);
                    if (m_P.Count == 0 || (q - m_P[m_P.Count - 1]).sqrMagnitude > 0.01f) m_P.Add(q);
                }
                m_S = new float[m_P.Count];
                for (int i = 1; i < m_P.Count; i++) m_S[i] = m_S[i - 1] + Vector3.Distance(m_P[i - 1], m_P[i]);
            }
            public Vector3 At(float s)
            {
                if (s <= 0f) return m_P[0];
                for (int i = 0; i < m_P.Count - 1; i++)
                    if (s <= m_S[i + 1]) return Vector3.Lerp(m_P[i], m_P[i + 1], (s - m_S[i]) / Mathf.Max(0.001f, m_S[i + 1] - m_S[i]));
                return m_P[m_P.Count - 1];
            }
            public float Project(Vector3 pos, float from, float to)
            {
                pos.y = 0f;
                float best = float.MaxValue, bestS = from;
                for (int i = 0; i < m_P.Count - 1; i++)
                {
                    if (m_S[i + 1] < from || m_S[i] > to) continue;
                    Vector3 ab = m_P[i + 1] - m_P[i];
                    float k = Mathf.Clamp01(Vector3.Dot(pos - m_P[i], ab) / Mathf.Max(0.0001f, ab.sqrMagnitude));
                    float s = Mathf.Clamp(m_S[i] + k * ab.magnitude, from, to);
                    float d = (At(s) - pos).sqrMagnitude;
                    if (d < best) { best = d; bestS = s; }
                }
                return bestS;
            }
            public float TurnBetween(float s0, float s1)
            {
                float total = 0f;
                Vector3 prev = Vector3.zero;
                for (float s = s0; s < s1; s += 1.5f)
                {
                    Vector3 d = At(s + 1.5f) - At(s);
                    if (d.sqrMagnitude < 0.0001f) continue;
                    if (prev != Vector3.zero) total += Vector3.Angle(prev, d);
                    prev = d;
                }
                return total;
            }
        }

        IEnumerator EnterCar()
        {
            var car = CourierVehicle.Instance;
            var rigs = PlayerRigs.Instance;
            rigs.TeleportTo(car.exitLeft.position, car.transform.eulerAngles.y + 90f);
            yield return Wait(0.2f);
            car.RequestEnter();
            float t = 0f;
            while ((!car.HasDriver || car.Busy) && t < 4f) { t += Time.deltaTime; yield return null; }
            Log("car entered: " + car.HasDriver);
        }

        /// <summary>Drives the demo route (depot to substation) with real W/A/S/D keys until stopped.</summary>
        IEnumerator Drive(float maxSpeed)
        {
            var car = CourierVehicle.Instance;
            var cells = Root.City.FindRoute("depot", "substation");
            if (cells == null) { Log("no route to drive"); yield break; }
            var pts = RouteValidator.PathToWorld(cells, 2f, 0f);
            var goal = SceneRegistry.Get("substation.park");
            if (goal != null) pts.Add(goal.position);
            var line = new Line(pts);
            var kb = Keyboard.current;
            float s = line.Project(car.Position, 0f, 14f);
            var body = car.GetComponent<Rigidbody>();
            int mask = LayerMask.GetMask("Vehicle");
            m_Driving = true;
            while (m_Driving && car.HasDriver && car.DistanceTo("substation.park") > 6.5f)
            {
                float v = car.Speed;
                s = line.Project(car.Position, Mathf.Max(0f, s - 1f), s + 10f);
                Vector3 aim = line.At(s + 3.5f + Mathf.Abs(v) * 0.45f);
                Vector3 to = aim - new Vector3(car.Position.x, 0f, car.Position.z);
                Vector3 fwd = car.transform.forward; fwd.y = 0f;
                float angle = Vector3.SignedAngle(fwd, to, Vector3.up);
                float turn = line.TurnBetween(s, s + 6f + Mathf.Abs(v) * 1.3f);
                float targetV = Mathf.Lerp(maxSpeed, 4.5f, Mathf.InverseLerp(12f, 70f, turn));
                float toGoal = car.DistanceTo("substation.park");
                if (toGoal < 16f) targetV = Mathf.Min(targetV, 1.8f + toGoal * 0.35f);
                if (Physics.SphereCast(car.Position + Vector3.up * 0.9f + car.transform.forward * 2f, 0.55f, car.transform.forward, out var hit,
                        4f + Mathf.Abs(v) * 1.2f, mask, QueryTriggerInteraction.Ignore) && hit.rigidbody != body)
                    targetV = Mathf.Min(targetV, Mathf.Max(0f, hit.distance - 2.5f) * 0.6f);
                var keys = new List<Key>();
                if (v < targetV - 0.3f) keys.Add(Key.W);
                else if (v > targetV + 1.2f) keys.Add(Key.S);
                if (angle > 3f) keys.Add(Key.D);
                else if (angle < -3f) keys.Add(Key.A);
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(keys.ToArray()));
                yield return null;
            }
            // Park.
            float b = 0f;
            while (Mathf.Abs(car.Speed) > 0.2f && b < 4f)
            {
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(Key.Space));
                b += Time.deltaTime;
                yield return null;
            }
            if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState());
            m_Driving = false;
        }

        void StopDriving()
        {
            m_Driving = false;
            var kb = Keyboard.current;
            if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState());
        }

        /// <summary>Gets the aircraft rolling: power, beacons, then departure clearance.</summary>
        IEnumerator ClearForTakeoff()
        {
            yield return PlaceBridgeNow();
            PowerUp();
            yield return Wait(0.3f);
            BeaconSystem.Instance.masterSwitch.Interact(InteractorKind.Desktop);
            float t = 0f;
            while (!AircraftSequence.Instance.ConditionsMet && t < 10f) { t += Time.deltaTime; yield return null; }
            Root.City.SetFlag(Flags.DepartureCleared, true);
            Log("departure cleared; aircraft " + AircraftSequence.Instance.State);
        }

        // ------------------------------------------------------------------ shots
        void Register()
        {
            m_Shots["A1"] = ShotMiniGlide;
            m_Shots["A2"] = ShotReveal;
            m_Shots["A3"] = ShotPlacement;
            m_Shots["A4"] = ShotBridgeRise;
            m_Shots["B1"] = ShotFoldSwoop;
            m_Shots["B2"] = ShotCellLoad;
            m_Shots["B3"] = () => ShotDrive("B3");
            m_Shots["B4"] = () => ShotDrive("B4");
            m_Shots["B5"] = () => ShotDrive("B5");
            m_Shots["B6"] = ShotSubstation;
            m_Shots["C1"] = ShotStorm;
            m_Shots["C2"] = ShotBeacons;
            m_Shots["C3"] = ShotBoarding;
            m_Shots["C4"] = ShotLever;
            m_Shots["C5"] = ShotTakeoffHeadOn;
            m_Shots["C6"] = ShotTakeoffChase;
        }

        // A1: tilt-shift glide over the miniature towards the broken east causeway. The path follows the
        // island road (row 5), which has no buildings to fly through.
        IEnumerator ShotMiniGlide()
        {
            yield return Fresh(false, 0.05f);
            Vector3 focus = Mini(152f, 0f, 72f);
            yield return Record("A1", 7f, 5.5f, t =>
            {
                float e = Smooth(t);
                Vector3 pos = Lerp3(Mini(F(104f, 112f), F(13f, 14f), 88.5f), Mini(F(139f, 141f), 7.5f, 88f), e);
                Vector3 look = Lerp3(Mini(148f, 0f, 70f), Mini(153f, 0f, 72.5f), e);
                Pose(pos, look, F(40f, 62f), 0.003f);
                Dof(Vector3.Distance(pos, focus), 2.0f, 50f);
            });
        }

        // A2: pull back from inside the miniature to the plinth, the terrace and the real city below.
        IEnumerator ShotReveal()
        {
            yield return Fresh(false, 0.05f);
            Vector3 p0 = Mini(96f, 34f, 34f), l0 = Mini(98f, 0f, 84f);
            Vector3 p1 = new Vector3(95.2f, 24.55f, -48.3f), l1 = new Vector3(97f, 12f, 30f);
            Quaternion r0 = Quaternion.LookRotation(l0 - p0), r1 = Quaternion.LookRotation(l1 - p1);
            yield return Record("A2", 7f, 5.5f, t =>
            {
                float e = InOutCubic(t);
                Vector3 pos = Lerp3(p0, p1, e);
                m_Cam.transform.position = pos;
                m_Cam.transform.rotation = Quaternion.Slerp(r0, r1, InOutCubic(Range01(t, 0.05f, 0.95f)));
                m_Cam.fieldOfView = Mathf.Lerp(F(44f, 66f), F(52f, 74f), e);
                m_Cam.nearClipPlane = Mathf.Lerp(0.003f, 0.05f, e);
                float focus = Vector3.Distance(pos, Mini(98f, 0f, 70f));
                Dof(focus, Mathf.Lerp(2.0f, 16f, e), 50f, 1f - Range01(t, 0.45f, 0.8f));
            });
        }

        // A3: macro placement over the channel. Held the wrong way round (coral ghost), one quarter turn
        // (teal ghost), lowered, set in. Landscape looks east along the channel; portrait looks in from the
        // island road so the bridge fits the narrow frame.
        IEnumerator ShotPlacement()
        {
            yield return Fresh(false, 0.05f);
            var tt = TabletopController.Instance;
            var piece = tt.Piece("piece.bridge");
            var socket = MiniCity.Instance.Socket("bridge_east");
            Vector3 s = socket.transform.position;
            tt.BeginHold(piece);
            piece.BeginDesktopHold();
            int good = ValidQuarter(piece);
            TurnTo(piece, good + 1); // wrong way round first
            Vector3 start = Mini(F(144f, 160f), F(15f, 17f), F(79f, 81f));
            piece.transform.SetPositionAndRotation(start, QuarterRotation(piece.CurrentQuarter));
            Vector3 hover = s + Vector3.up * 0.036f;
            bool turned = false, released = false;
            Vector3 c0 = Mini(F(133.5f, 138f), F(10.5f, 11.5f), F(66.5f, 88f)), c1 = Mini(F(136.5f, 140f), F(9f, 10f), F(70.5f, 86.5f));
            Vector3 look = Mini(152f, 3f, 72.3f);
            yield return Record("A3", 7f, 6f, t =>
            {
                if (!released)
                {
                    Vector3 target;
                    if (t < 0.2f) target = Lerp3(start, hover, OutCubic(Range01(t, 0f, 0.2f)));
                    else if (t < 0.6f) target = hover + Vector3.up * (Mathf.Sin((t - 0.2f) * 18f) * 0.0012f);
                    else target = Lerp3(hover, s + Vector3.up * 0.004f, Smooth(Range01(t, 0.6f, 0.74f)));
                    if (!turned && t >= 0.44f) { TurnTo(piece, good); turned = true; }
                    HoldPiece(piece, target, t < 0.2f ? 30f : 14f);
                    if (t >= 0.76f)
                    {
                        ReleaseIntoSocket(piece, socket);
                        released = true;
                        Log("A3 bridge placed: " + !Root.City.GetPlacement("bridge_east").IsEmpty);
                    }
                }
                Vector3 pos = Lerp3(c0, c1, Smooth(t));
                Pose(pos, look, F(36f, 54f), 0.003f);
                Dof(Vector3.Distance(pos, s + Vector3.up * 0.012f), 2.4f, 50f);
            });
        }

        // A4: the real bridge rises out of the sea and locks in. Low over the water.
        IEnumerator ShotBridgeRise()
        {
            yield return Fresh(false, 0.06f);
            var slot = Slot("bridge_east");
            if (slot != null) slot.buildDuration = 3.4f;
            bool placed = false;
            yield return Record("A4", 7f, 6f, t =>
            {
                if (!placed && t >= 0.16f) { placed = true; StartCoroutine(PlaceBridgeNow()); }
                Vector3 pos = Lerp3(new Vector3(F(133.5f, 136f), -0.5f, F(66.5f, 66f)), new Vector3(F(137.5f, 139f), -0.25f, F(68.5f, 67.5f)), Smooth(t));
                Pose(pos, new Vector3(152f, F(0.6f, 2.2f), 72.5f), F(52f, 74f));
            });
            if (slot != null) slot.buildDuration = 1.6f;
        }

        // B1: the fold. From high over the depot down to eye level beside the courier car; NURI darts in.
        IEnumerator ShotFoldSwoop()
        {
            yield return Fresh(true, 0.1f);
            yield return PlaceBridgeNow();
            var rigs = PlayerRigs.Instance;
            Vector3 eye = new Vector3(133.6f, 1.65f, 24.8f), car = new Vector3(136f, 0.9f, 30.5f);
            rigs.TeleportTo(new Vector3(eye.x, 0.15f, eye.z), Mathf.Atan2(car.x - eye.x, car.z - eye.z) * Mathf.Rad2Deg);
            yield return Wait(0.6f);
            Vector3 p0 = new Vector3(126f, 58f, -2f);
            Quaternion r0 = Quaternion.LookRotation(new Vector3(137f, 0f, 30f) - p0), r1 = Quaternion.LookRotation(car - eye);
            yield return Record("B1", 5f, 4.5f, t =>
            {
                float e = InOutCubic(t);
                Vector3 pos = Vector3.Lerp(p0, eye, e);
                pos.y = Mathf.Lerp(p0.y, eye.y, Mathf.Pow(e, 0.8f));
                m_Cam.transform.position = pos;
                m_Cam.transform.rotation = Quaternion.Slerp(r0, r1, InOutCubic(Range01(t, 0.25f, 1f)));
                m_Cam.fieldOfView = Mathf.Lerp(F(58f, 80f), F(68f, 84f), e);
                m_Cam.nearClipPlane = 0.05f;
            });
        }

        // B2: the glowing power cell swings into the courier car's cradle.
        IEnumerator ShotCellLoad()
        {
            yield return Fresh(true, 0.12f);
            var car = CourierVehicle.Instance;
            var cell = PowerCell.Instance;
            cell.Interact(InteractorKind.Desktop); // out of the dock, as the player does
            cell.transform.SetParent(null, true);
            Vector3 cradle = car.cradle.transform.position;
            Vector3 a = cradle + car.transform.right * 1.3f + Vector3.up * 0.55f - car.transform.forward * 0.9f;
            cell.transform.position = a;
            bool inserted = false;
            yield return Record("B2", 4f, 3.5f, t =>
            {
                if (!inserted)
                {
                    float e = InOutCubic(Range01(t, 0.08f, 0.62f));
                    Vector3 p = Vector3.Lerp(a, cradle, e) + Vector3.up * Mathf.Sin(e * Mathf.PI) * 0.35f;
                    cell.transform.position = p;
                    cell.transform.rotation = Quaternion.Euler(0f, car.transform.eulerAngles.y + (1f - e) * 40f, (1f - e) * -14f);
                    if (t >= 0.64f) { cell.InsertInto(car.cradle); inserted = true; }
                }
                Vector3 pos = cradle + car.transform.right * F(2.3f, 1.9f) - car.transform.forward * F(1.8f, 1.5f) + Vector3.up * F(0.55f, 0.75f);
                pos += car.transform.forward * Mathf.Lerp(0f, 0.35f, t);
                Pose(pos, cradle + Vector3.up * 0.25f, F(38f, 56f));
                Dof(Vector3.Distance(pos, cradle), 3.2f, 60f);
            });
            NoDof();
        }

        // B3/B4/B5: the courier car crosses the bridge the player built (three camera angles, three drives).
        IEnumerator ShotDrive(string id)
        {
            yield return Fresh(true, 0.14f);
            yield return PlaceBridgeNow();
            yield return Wait(2.2f); // let the bridge finish rising
            yield return EnterCar();
            var car = CourierVehicle.Instance;
            StartCoroutine(Drive(10.5f));
            // Start filming as the car turns towards the bridge.
            float wait = 0f;
            float startZ = id == "B3" ? 49f : (id == "B4" ? 61f : 58f);
            while (car.Position.z < startZ && wait < 30f) { wait += Time.deltaTime; yield return null; }
            Vector3 vel = Vector3.zero, smoothPos = car.Position - car.transform.forward * 7f + Vector3.up * 2.4f;
            if (id == "B3")
            {
                yield return Record("B3", 7f, 6f, t =>
                {
                    Vector3 fwd = car.transform.forward; fwd.y = 0f; fwd.Normalize();
                    Vector3 right = Vector3.Cross(Vector3.up, fwd);
                    Vector3 want = car.Position - fwd * F(7.5f, 6.5f) + Vector3.up * F(2.3f, 2.6f) + right * 0.9f;
                    smoothPos = Vector3.SmoothDamp(smoothPos, want, ref vel, 0.22f, Mathf.Infinity, 1f / Fps);
                    Pose(smoothPos, car.Position + fwd * 7f + Vector3.up * 0.8f, F(58f, 78f));
                });
            }
            else if (id == "B4")
            {
                float z = car.Position.z;
                yield return Record("B4", 5f, 4f, t =>
                {
                    z = Mathf.Lerp(z, car.Position.z + 2.5f, 1f - Mathf.Exp(-6f / Fps));
                    Vector3 pos = new Vector3(F(140f, 142.5f), F(1.4f, 1.8f), z);
                    Pose(pos, car.Position + Vector3.up * 0.7f, F(34f, 56f));
                });
            }
            else
            {
                // Low on the island quay beside the bridge end: the car comes over the water at the lens.
                Vector3 cam = new Vector3(F(146.6f, 147.4f), 0.55f, 82.3f);
                Vector3 look = new Vector3(152.6f, 0.9f, 68f);
                yield return Record("B5", 4f, 3.5f, t =>
                {
                    look = Vector3.Lerp(look, car.Position + Vector3.up * 0.8f, 1f - Mathf.Exp(-4f / Fps));
                    Pose(cam + Vector3.up * t * 0.1f, look, F(50f, 70f));
                });
            }
            StopDriving();
        }

        // B6: the cell goes into the substation and the island wakes up.
        IEnumerator ShotSubstation()
        {
            yield return Fresh(true, 0.45f);
            yield return PlaceBridgeNow();
            var socket = Substation.Instance.socket;
            var cell = PowerCell.Instance;
            cell.Interact(InteractorKind.Desktop); // out of the dock, as the player does
            cell.transform.SetParent(null, true);
            Vector3 s = socket.attach.position;
            Vector3 a = s + new Vector3(1.5f, 0.45f, -1.7f);
            cell.transform.position = a;
            bool inserted = false;
            yield return Record("B6", 4f, 3.5f, t =>
            {
                if (!inserted)
                {
                    float e = InOutCubic(Range01(t, 0.06f, 0.46f));
                    cell.transform.position = Vector3.Lerp(a, s, e) + Vector3.up * Mathf.Sin(e * Mathf.PI) * 0.3f;
                    cell.transform.rotation = socket.attach.rotation * Quaternion.Euler(0f, (1f - e) * 50f, (1f - e) * 12f);
                    if (t >= 0.48f) { cell.InsertInto(socket); inserted = true; }
                }
                Vector3 pos = Lerp3(s + new Vector3(F(-3.2f, -2.4f), 0.45f, F(-4.6f, -4.9f)), s + new Vector3(F(-2.0f, -1.5f), 0.6f, F(-4.2f, -4.5f)), Smooth(t));
                Pose(pos, s + new Vector3(0.2f, 0.15f, 0.6f), F(44f, 62f));
                Dof(Vector3.Distance(pos, s), 4f, 50f);
            });
            NoDof();
        }

        // C1: the storm rolls in over the airfield (time-lapse).
        IEnumerator ShotStorm()
        {
            yield return Fresh(true, 0.15f);
            yield return PlaceBridgeNow();
            yield return Record("C1", 7f, 5.5f, t =>
            {
                m_Storm = Mathf.Lerp(0.15f, 0.9f, Smooth(t));
                Vector3 pos = Lerp3(new Vector3(112f, 4.2f, 126f), new Vector3(116f, 4.6f, 128.5f), t);
                Pose(pos, new Vector3(F(300f, 260f), F(46f, 70f), 300f), F(52f, 74f));
            });
        }

        // C2: runway beacons race away from the camera in the storm light.
        IEnumerator ShotBeacons()
        {
            yield return Fresh(true, 0.84f);
            yield return PlaceBridgeNow();
            PowerUp();
            var beacons = BeaconSystem.Instance;
            bool lit = false;
            const float sweepAt = 0.2f;
            yield return Record("C2", 5f, 4f, t =>
            {
                if (!lit && t >= sweepAt) { lit = true; beacons.masterSwitch.Interact(InteractorKind.Desktop); }
                // One sweep racing away from the lens (the game lights its three groups side by side).
                float since = (t - sweepAt) * m_RecDur;
                foreach (var g in beacons.groups)
                {
                    foreach (var r in g.lenses) if (r != null) SetBeaconLens(r, since >= (r.transform.position.x - 22f) / 95f);
                    foreach (var l in g.lights) if (l != null) l.enabled = since >= (l.transform.position.x - 22f) / 95f;
                }
                Vector3 pos = Lerp3(new Vector3(17.2f, F(0.62f, 0.85f), F(131.4f, 130f)), new Vector3(F(20.5f, 20f), F(0.7f, 0.9f), F(131.6f, 130.1f)), Smooth(t));
                Pose(pos, new Vector3(140f, F(1.4f, 1f), F(133.2f, 132.5f)), F(30f, 50f));
            });
        }

        // C3: the convoy is in; passengers walk out to the aircraft.
        IEnumerator ShotBoarding()
        {
            yield return Fresh(true, 0.6f);
            yield return PlaceBridgeNow();
            var plane = AircraftSequence.Instance;
            plane.RequireConvoy = true;
            PowerUp();
            BeaconSystem.Instance.masterSwitch.Interact(InteractorKind.Desktop);
            yield return Wait(0.3f);
            ConvoyDirector.Instance.PlaceAtTerminal();
            float w = 0f;
            while (plane.State != AircraftState.Boarding && w < 5f) { w += Time.deltaTime; yield return null; }
            Log("aircraft state for boarding: " + plane.State);
            // From the apron in front of the aircraft's nose: passengers cross from the shuttles to the door.
            yield return Record("C3", 5f, 4f, t =>
            {
                Vector3 pos = Lerp3(new Vector3(75.5f, 1.9f, F(113.8f, 114.5f)), new Vector3(77.2f, 2.05f, F(114.6f, 115f)), Smooth(t));
                Pose(pos, new Vector3(95f, 1.5f, 116.6f), F(46f, 66f));
            });
            plane.RequireConvoy = false;
        }

        // C4: the departure lever is thrown at the tower.
        IEnumerator ShotLever()
        {
            yield return Fresh(true, 0.86f);
            var lever = FindAnyObjectByType<DepartureLever>();
            Vector3 l = lever.transform.position;
            bool pulled = false;
            yield return Record("C4", 3f, 2.5f, t =>
            {
                if (!pulled && t >= 0.3f) { pulled = true; lever.Interact(InteractorKind.Desktop); }
                Vector3 fwd = lever.transform.forward;
                Vector3 pos = l + fwd * F(1.05f, 1.15f) + Vector3.up * F(1.05f, 1.2f) + lever.transform.right * F(0.45f, 0.35f) - fwd * t * 0.12f;
                Pose(pos, l + Vector3.up * 0.82f, F(38f, 56f));
            });
        }

        // C5: head-on from the far end of the runway, in the rain: the aircraft rolls at the lens, lifts and
        // passes just overhead.
        IEnumerator ShotTakeoffHeadOn()
        {
            yield return Fresh(true, 0.86f);
            yield return ClearForTakeoff();
            var plane = AircraftSequence.Instance;
            float w = 0f;
            while (plane.State != AircraftState.TakeoffRoll && w < 60f) { w += Time.deltaTime; yield return null; }
            Log($"takeoff roll at game t={Time.time:0.0}s");
            yield return Wait(F(0.6f, 1.6f));
            Vector3 cam = new Vector3(171.5f, 0.7f, F(140f, 139.6f));
            yield return Record("C5", 7f, 6f, t =>
            {
                Vector3 look = Vector3.Lerp(new Vector3(100f, F(3.2f, 5.5f), 135.4f), new Vector3(100f, F(9f, 14f), 135.4f), Smooth(t));
                Pose(cam + Vector3.up * t * 0.12f, look, F(42f, 64f));
            });
            Log($"C5 end: aircraft at {plane.transform.position}");
        }

        // C6: chase the aircraft up into the storm. The camera rides a fixed offset (smoothed in direction
        // only) that slowly lengthens, so the aircraft pulls away into the weather.
        IEnumerator ShotTakeoffChase()
        {
            yield return Fresh(true, 0.88f);
            yield return ClearForTakeoff();
            var plane = AircraftSequence.Instance;
            float w = 0f;
            while (plane.State != AircraftState.TakeoffRoll && w < 60f) { w += Time.deltaTime; yield return null; }
            // A beat before lift-off.
            w = 0f;
            while (plane.transform.position.x < 104f && w < 20f) { w += Time.deltaTime; yield return null; }
            Transform tr = plane.transform;
            Vector3 Flat(Vector3 v) { v.y = 0f; return v.sqrMagnitude > 1e-6f ? v.normalized : Vector3.forward; }
            Vector3 OffsetAt(float t)
            {
                Vector3 f = Flat(tr.forward), side = Vector3.Cross(Vector3.up, f);
                float e = Smooth(t);
                return -f * Mathf.Lerp(F(20f, 24f), F(42f, 46f), e) + Vector3.up * Mathf.Lerp(F(2.6f, 2.2f), F(-2f, -3f), e) + side * F(6f, 4f);
            }
            Vector3 offset = OffsetAt(0f), offVel = Vector3.zero;
            yield return Record("C6", 7f, 6f, t =>
            {
                offset = Vector3.SmoothDamp(offset, OffsetAt(t), ref offVel, 0.5f, Mathf.Infinity, 1f / Fps);
                Vector3 pos = tr.position + offset;
                pos.y = Mathf.Max(pos.y, 0.8f);
                Pose(pos, tr.position + tr.forward * 10f + Vector3.up * 1.5f, F(50f, 72f));
            });
        }
    }
}
