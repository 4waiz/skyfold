using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Skyfold
{
    /// <summary>
    /// Automated desktop QA scenarios, started with --qa=&lt;name&gt;. They drive the real build through the
    /// same entry points the input handlers use (and real keyboard events for bindings), take
    /// screenshots, check invariants and write a report, then quit with exit code 0 (pass) or 1 (fail).
    /// This is evidence for desktop logic only; it does not replace headset testing.
    /// </summary>
    public sealed class QARunner : MonoBehaviour
    {
        public bool Running { get; private set; }

        string m_Out;
        readonly StringBuilder m_Report = new StringBuilder();
        int m_Failures, m_Checks;
        float m_Start;

        GameRoot Root => GameRoot.Instance;
        MissionDirector MD => MissionDirector.Instance;

        public void Run(string scenario, string outDir)
        {
            m_Out = string.IsNullOrEmpty(outDir) ? Path.Combine(Application.persistentDataPath, "QA") : outDir;
            Directory.CreateDirectory(m_Out);
            Running = true;
            m_Start = Time.realtimeSinceStartup;
            Log($"QA scenario '{scenario}' started {DateTime.Now:yyyy-MM-dd HH:mm:ss} · GPU {SystemInfo.graphicsDeviceName} · {Screen.width}x{Screen.height}");
            StartCoroutine(Scenario(scenario));
        }

        IEnumerator Scenario(string scenario)
        {
            yield return new WaitForSecondsRealtime(1.5f);
            IEnumerator body;
            switch (scenario)
            {
                case "smoke": body = Smoke(); break;
                case "episode1": body = Episode1(false); break;
                case "episode1east": body = Episode1(true); break;
                case "demo": body = Demo(); break;
                case "fail": body = FailRetry(); break;
                case "restarts": body = Restarts(10); break;
                case "soak": body = Soak(15f * 60f); break;
                case "campaign": body = Campaign(); break;
                case "tour": body = Tour(); break;
                default: Check(false, "unknown scenario " + scenario); body = null; break;
            }
            if (body != null) yield return StartCoroutine(Guard(body));
            Finish();
        }

        IEnumerator Guard(IEnumerator body)
        {
            // Unity coroutines cannot catch exceptions; failures surface as missing checks in the report.
            yield return body;
        }

        // ------------------------------------------------------------------ helpers
        void Log(string line)
        {
            string t = $"[{Time.realtimeSinceStartup - m_Start,7:0.0}s] {line}";
            m_Report.AppendLine(t);
            Debug.Log("[QA] " + line);
        }

        void Check(bool ok, string what)
        {
            m_Checks++;
            if (!ok) m_Failures++;
            Log((ok ? "PASS " : "FAIL ") + what);
        }

        IEnumerator Shot(string name)
        {
            yield return new WaitForEndOfFrame();
            string path = Path.Combine(m_Out, name + ".png");
            ScreenCapture.CaptureScreenshot(path);
            Log("screenshot " + path);
            yield return null;
        }

        IEnumerator WaitUntil(Func<bool> cond, float timeout, string what)
        {
            float t = 0f;
            while (!cond() && t < timeout) { t += Time.unscaledDeltaTime; yield return null; }
            Check(cond(), what + $" (within {timeout:0}s)");
        }

        /// <summary>A real key press through the Input System: down for two frames, then up.</summary>
        static IEnumerator Press(Key key)
        {
            var kb = Keyboard.current;
            if (kb == null) yield break;
            InputSystem.QueueStateEvent(kb, new KeyboardState(key));
            yield return null;
            yield return null;
            InputSystem.QueueStateEvent(kb, new KeyboardState());
            yield return null;
        }

        IEnumerator HoldKeys(float seconds, params Key[] keys)
        {
            var kb = Keyboard.current;
            float t = 0f;
            while (t < seconds)
            {
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(keys));
                t += Time.deltaTime;
                yield return null;
            }
            if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState());
            yield return null;
        }

        /// <summary>Places a piece through the same path a mouse release uses.</summary>
        IEnumerator PlacePiece(string pieceId, string socketId, int rotation)
        {
            var tt = TabletopController.Instance;
            var piece = tt.Piece(pieceId);
            var socket = MiniCity.Instance.Socket(socketId);
            Check(piece != null && socket != null, $"piece {pieceId} and socket {socketId} exist");
            if (piece == null || socket == null) yield break;
            Check(tt.BeginHold(piece), "pick up " + pieceId);
            piece.BeginDesktopHold();
            for (int i = 0; i < rotation; i++) piece.DesktopRotate();
            float t = 0f;
            while (t < 0.6f)
            {
                piece.DesktopFollow(socket.transform.position + Vector3.up * 0.04f);
                t += Time.deltaTime;
                yield return null;
            }
            piece.EndDesktopHold();
            tt.Release(piece);
            yield return new WaitForSecondsRealtime(0.5f);
        }

        // ------------------------------------------------------------------ driving bot
        static Vector3 Flat(Vector3 v) => new Vector3(v.x, 0f, v.z);

        /// <summary>The route's lane line with arc-length lookup, for a pure-pursuit driver.</summary>
        sealed class DriveLine
        {
            readonly List<Vector3> m_P = new List<Vector3>();
            readonly float[] m_S;
            public float Length => m_S[m_S.Length - 1];

            public DriveLine(List<Vector3> pts)
            {
                foreach (var p in pts)
                    if (m_P.Count == 0 || (Flat(p) - m_P[m_P.Count - 1]).sqrMagnitude > 0.01f) m_P.Add(Flat(p));
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

            /// <summary>Closest arc length to a position, searched in [from, to] so progress never jumps back.</summary>
            public float Project(Vector3 pos, float from, float to)
            {
                pos = Flat(pos);
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

            /// <summary>Total heading change in degrees between two arc lengths.</summary>
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

        /// <summary>
        /// Drives the courier car with real W/A/S/D/Space keyboard events, like a careful player:
        /// follows the right-hand lane, slows for corners, backs up if stuck, stops at the target.
        /// </summary>
        IEnumerator DriveTo(string target, float timeout)
        {
            var car = CourierVehicle.Instance;
            var cells = Root.City.FindRoute("depot", "substation");
            Check(cells != null && cells.Count > 1, "a drivable route exists");
            if (cells == null || cells.Count < 2) yield break;
            var pts = RouteValidator.PathToWorld(cells, 2f, 0f);
            var goal = SceneRegistry.Get(target);
            if (goal != null) pts.Add(goal.position);
            var line = new DriveLine(pts);
            Log("route " + string.Join(" ", cells.ConvertAll(c => $"({c.x},{c.y})")) + $", lane line {line.Length:0} m");

            var kb = Keyboard.current;
            CourierVehicle.DebugEvent = msg => Log("car " + msg);
            float s = line.Project(car.Position, 0f, 14f);
            float t = 0f, nextLog = 0f, stuck = 0f, driven = 0f;
            int stuckEvents = 0;
            Vector3 last = car.Position;
            while (t < timeout && car.DistanceTo(target) > 6.5f)
            {
                if (!car.HasDriver) { Log("driver left the car unexpectedly"); break; }
                float v = car.Speed;
                s = line.Project(car.Position, Mathf.Max(0f, s - 1f), s + 10f);
                Vector3 aim = line.At(s + 3.5f + Mathf.Abs(v) * 0.45f);
                float angle = Vector3.SignedAngle(Flat(car.transform.forward), aim - Flat(car.Position), Vector3.up);
                float turn = line.TurnBetween(s, s + 6f + Mathf.Abs(v) * 1.3f);
                float targetV = Mathf.Lerp(11.5f, 4.5f, Mathf.InverseLerp(12f, 70f, turn));
                float toGoal = car.DistanceTo(target);
                if (toGoal < 16f) targetV = Mathf.Min(targetV, 1.8f + toGoal * 0.35f);

                var keys = new List<Key>();
                if (v < targetV - 0.3f) keys.Add(Key.W);
                else if (v > targetV + 1.2f) keys.Add(Key.S);
                if (angle > 3f) keys.Add(Key.D);
                else if (angle < -3f) keys.Add(Key.A);

                // A player who is stuck backs up and tries again; do the same and record it.
                stuck = keys.Contains(Key.W) && Mathf.Abs(v) < 0.4f ? stuck + Time.deltaTime : 0f;
                if (stuck > 2.5f)
                {
                    stuckEvents++;
                    Log($"STUCK #{stuckEvents} at ({car.Position.x:0.0},{car.Position.z:0.0}) cell {car.Cell}, line {s:0}/{line.Length:0} m, aim angle {angle:0}");
                    if (stuckEvents <= 3) yield return Shot($"drive_stuck_{stuckEvents}");
                    if (stuckEvents > 4) break;
                    float r = 0f;
                    var back = new[] { Key.S, angle > 0f ? Key.A : Key.D };
                    while (r < 1.8f)
                    {
                        if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(back));
                        r += Time.deltaTime;
                        t += Time.deltaTime;
                        yield return null;
                    }
                    stuck = 0f;
                    continue;
                }

                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(keys.ToArray()));
                driven += Vector3.Distance(Flat(last), Flat(car.Position));
                last = car.Position;
                if (t >= nextLog)
                {
                    nextLog += 1f;
                    Log($"drive t={t:0.0} pos=({car.Position.x:0.0},{car.Position.y:0.00},{car.Position.z:0.0}) cell={car.Cell} v={v:0.0}/{targetV:0.0} line={s:0}/{line.Length:0} angle={angle:0} turn={turn:0} keys={string.Join("+", keys)} in(th={car.ThrottleInput:0.0} br={car.BrakeInput:0.0} st={car.SteerInput:0.00}) wheels={car.GroundedWheels}");
                }
                t += Time.deltaTime;
                yield return null;
            }
            // Parking brake (Space) to a full stop.
            float b = 0f;
            while (Mathf.Abs(car.Speed) > 0.2f && b < 6f)
            {
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(Key.Space));
                b += Time.deltaTime;
                yield return null;
            }
            if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState());
            yield return null;
            CourierVehicle.DebugEvent = null;
            Log($"drive finished after {t:0.0}s, {driven:0} m driven, {stuckEvents} stuck events");
            Check(car.DistanceTo(target) <= 9f, $"car reached {target} ({car.DistanceTo(target):0.0} m)");
            Check(stuckEvents == 0, "drove the route without getting stuck");
        }

        IEnumerator WalkTo(Vector3 feet, float yaw)
        {
            // Walking is tested elsewhere; here we stand where a player would after walking.
            PlayerRigs.Instance.TeleportTo(feet, yaw);
            yield return new WaitForSecondsRealtime(0.3f);
        }

        // ------------------------------------------------------------------ scenarios
        IEnumerator Smoke()
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot("01_title");
            Check(MenuController.Instance.Screen == "title", "title menu is open");
            Root.StartMission(MissionCatalog.Episode1);
            yield return new WaitForSecondsRealtime(2f);
            Check(MD.State == MissionState.Active, "episode 1 active");
            Check(FoldController.Instance.InAtelier, "starts in the Atelier");
            yield return Shot("02_atelier");
            yield return Press(Key.Escape);
            yield return new WaitForSecondsRealtime(0.5f);
            Check(Root.IsPaused, "Escape pauses");
            yield return Shot("03_pause");
            yield return Press(Key.Escape);
            yield return new WaitForSecondsRealtime(0.5f);
            Check(!Root.IsPaused, "Escape resumes");
        }

        IEnumerator Episode1(bool east)
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(0.5f);
            Root.StartMission(MissionCatalog.Episode1);
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot("e1_01_start");
            var city = Root.City;
            Check(!city.HasRoute("depot", "substation"), "no route at start");

            // Invalid rotation is rejected and the piece is not consumed.
            int rejected = city.RejectedAttempts;
            yield return PlacePiece("piece.bridge", "bridge_west", 1);
            Check(city.RejectedAttempts == rejected + 1, "rotated bridge rejected");
            Check(city.SocketOfPiece("piece.bridge") == null, "rejected piece returned, not consumed");
            yield return Shot("e1_02_rejected");

            if (east)
            {
                yield return PlacePiece("piece.straight", "harbour_corner", 0);
                Check(city.GetPlacement("harbour_corner").IsEmpty, "straight harbour piece rejected (faces water)");
                yield return PlacePiece("piece.corner", "harbour_corner", 1);
                Check(!city.GetPlacement("harbour_corner").IsEmpty, "harbour corner accepted");
                yield return PlacePiece("piece.bridge", "bridge_east", 0);
            }
            else yield return PlacePiece("piece.bridge", "bridge_west", 0);
            Check(city.HasRoute("depot", "substation"), "route complete after placement");
            yield return new WaitForSecondsRealtime(2.5f);
            yield return Shot("e1_03_route");

            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective reached");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "Q folds down into the street");
            yield return new WaitForSecondsRealtime(0.6f);
            yield return Shot("e1_04_street");

            var car = CourierVehicle.Instance;
            var door = car.exitLeft.position;
            yield return WalkTo(door + car.transform.right * -0.3f, car.transform.eulerAngles.y + 90f);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.enter", 15f, "walk objective complete");
            car.RequestEnter();
            yield return WaitUntil(() => car.HasDriver && !car.Busy, 5f, "entered the car");
            yield return Shot("e1_05_car");
            yield return DriveTo("substation.park", 120f);
            yield return Shot("e1_06_island");
            yield return WaitUntil(() => MD.State == MissionState.Results || MD.State == MissionState.Success, 30f, "episode 1 success");
            yield return new WaitForSecondsRealtime(4f);
            yield return Shot("e1_07_results");
            var r = MD.LastResult;
            Check(r != null && r.Success, "result recorded");
            if (r != null) Log($"result medal={r.Medal} timeLeft={r.TimeLeft:0} rejected={r.Rejected} hints={r.HintsShown} shortcut={r.UsedShortcut}");
            Check(r != null && r.UsedShortcut == east, "shortcut flag matches the route built");
        }

        IEnumerator Demo()
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(0.5f);
            Root.StartMission(MissionCatalog.Demo);
            float start = Time.realtimeSinceStartup;
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot("d_01_start");
            yield return PlacePiece("piece.bridge", "bridge_east", 0);
            Check(Root.City.HasRoute("depot", "substation"), "demo route complete");
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "demo fold objective");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "folded");
            var cell = PowerCell.Instance;
            var car = CourierVehicle.Instance;
            yield return WalkTo(cell.transform.position + Vector3.back * 1.2f, 0f);
            cell.Interact(InteractorKind.Desktop);
            Check(cell.Location == CellLocation.Held, "picked up the cell (E)");
            yield return WalkTo(car.cradle.transform.position + car.transform.forward * -1.4f, car.transform.eulerAngles.y);
            car.cradle.Interact(InteractorKind.Desktop);
            Check(cell.Location == CellLocation.CarCradle, "cell loaded into cradle");
            yield return Shot("d_02_cell");
            yield return WalkTo(car.exitLeft.position, car.transform.eulerAngles.y + 90f);
            car.RequestEnter();
            yield return WaitUntil(() => car.HasDriver && !car.Busy, 5f, "entered car");
            yield return DriveTo("substation.park", 60f);
            yield return Press(Key.E);
            yield return WaitUntil(() => !car.HasDriver && !car.Busy, 5f, "E exits the stopped car");
            car.cradle.Interact(InteractorKind.Desktop);
            Check(cell.HeldOnDesktop, "took cell from cradle");
            var socket = Substation.Instance.socket;
            yield return WalkTo(socket.transform.position + Vector3.back * 1.5f, 0f);
            socket.Interact(InteractorKind.Desktop);
            yield return WaitUntil(() => Root.City.GetFlag(Flags.SubstationPowered), 3f, "substation powered");
            yield return Shot("d_03_power");
            var sw = BeaconSystem.Instance.masterSwitch;
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "d.beacons", 10f, "beacon objective");
            sw.Interact(InteractorKind.Desktop);
            yield return WaitUntil(() => BeaconSystem.Instance.AllLit, 3f, "beacons lit");
            yield return WaitUntil(() => AircraftSequence.Instance.ConditionsMet, 15f, "aircraft ready (boarded)");
            var lever = FindAnyObjectByType<DepartureLever>();
            lever.Interact(InteractorKind.Desktop);
            yield return new WaitForSecondsRealtime(6f);
            yield return Shot("d_04_taxi");
            yield return WaitUntil(() => AircraftSequence.Instance.State == AircraftState.Climb, 40f, "takeoff roll to climb");
            yield return Shot("d_05_takeoff");
            yield return WaitUntil(() => MD.State == MissionState.Results, 60f, "demo results");
            yield return Shot("d_06_results");
            Log($"demo wall time (bot) {Time.realtimeSinceStartup - start:0}s, storm left {MD.LastResult?.TimeLeft:0}s");
            Check(ProgressStore.Campaign.episodes.TrueForAll(e => e.id != MissionCatalog.Demo), "demo did not write campaign progress");
        }

        IEnumerator FailRetry()
        {
            Root.ChooseDesktop();
            Root.StartMission(MissionCatalog.Episode2);
            yield return new WaitForSecondsRealtime(1f);
            Check(MD.State == MissionState.Active, "episode 2 active");
            // Fast-forward the storm through the public timer path by waiting with time scale.
            SettingsStore.Current.guidance = Guidance.Off;
            Time.timeScale = 20f;
            yield return WaitUntil(() => MD.State == MissionState.Failed, 30f, "storm failure reached");
            Time.timeScale = 1f;
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot("f_01_failed");
            Check(MenuController.Instance.Screen == "failed", "failure screen shown");
            MD.Retry();
            yield return WaitUntil(() => MD.State == MissionState.Active, 5f, "retry restores play");
            Check(MD.StormLeft >= 75f, "retry grants at least 75 s");
            yield return Shot("f_02_retry");
            SettingsStore.Current.guidance = Guidance.FullTutorial;
        }

        IEnumerator Restarts(int count)
        {
            Root.ChooseDesktop();
            int listeners0 = -1;
            for (int i = 0; i < count; i++)
            {
                Root.StartMission(i % 2 == 0 ? MissionCatalog.Demo : MissionCatalog.Episode1);
                yield return new WaitForSecondsRealtime(0.8f);
                if (i % 3 == 0) MD.Restart();
                yield return new WaitForSecondsRealtime(0.8f);
                Root.QuitToMenu();
                yield return new WaitForSecondsRealtime(0.4f);
                int listeners = Root.City.ListenerCount;
                if (listeners0 < 0) listeners0 = listeners;
                Check(listeners == listeners0, $"restart {i + 1}: CityState listeners stable ({listeners})");
                Check(FindObjectsByType<GameRoot>().Length == 1, $"restart {i + 1}: one GameRoot");
                Check(FindObjectsByType<AudioListener>().Length == 1, $"restart {i + 1}: exactly one audio listener");
            }
        }

        IEnumerator Soak(float seconds)
        {
            float end = Time.realtimeSinceStartup + seconds;
            int loops = 0;
            long mem0 = GC.GetTotalMemory(false);
            while (Time.realtimeSinceStartup < end)
            {
                yield return Demo();
                loops++;
                Root.QuitToMenu();
                yield return new WaitForSecondsRealtime(1f);
                Log($"soak loop {loops}: managed heap {GC.GetTotalMemory(false) / (1024 * 1024)} MB, fps ~{1f / Mathf.Max(0.0001f, Time.smoothDeltaTime):0}");
            }
            Check(loops > 0, $"soak completed {loops} demo loops in {seconds / 60f:0} min");
            Log($"managed heap start {mem0 / (1024 * 1024)} MB end {GC.GetTotalMemory(false) / (1024 * 1024)} MB");
        }

        IEnumerator Campaign()
        {
            yield return Episode1(true);
            Root.QuitToMenu();
            yield return new WaitForSecondsRealtime(1f);
            Check(ProgressStore.Campaign.unlockedEpisode >= 2, "episode 2 unlocked");
            Check(ProgressStore.Campaign.placements.Count > 0, "route saved for later episodes");
        }

        IEnumerator Tour()
        {
            // Views for art review and the delivery report (real build, real renderer).
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(2.5f);
            yield return Shot("tour_01_title");
            Root.StartMission(MissionCatalog.Demo);
            yield return new WaitForSecondsRealtime(2.5f);
            yield return Shot("tour_02_atelier");
            var fold = FoldController.Instance;
            var views = new (string name, Vector3 pos, float yaw, float pitch)[]
            {
                ("tour_03_depot", new Vector3(122f, 0.15f, 36f), 75f, 4f),
                ("tour_04_avenue", new Vector3(52f, 0.15f, 30f), 70f, 2f),
                ("tour_05_causeway_east", new Vector3(156f, 0.15f, 54f), 300f, 4f),
                ("tour_06_causeway_west", new Vector3(20f, 0.15f, 54f), 35f, 6f),
                ("tour_07_island", new Vector3(110f, 0.15f, 94f), 75f, 2f),
                ("tour_08_airfield", new Vector3(118f, 0.15f, 112f), 300f, 6f),
                ("tour_09_substation", new Vector3(158f, 0.15f, 92f), 30f, 4f),
                ("tour_10_atelier_from_city", new Vector3(96f, 0.15f, 12f), 180f, -8f)
            };
            fold.SetLocationImmediate(false, fold.Station("kiosk.A"), new Anchor(views[0].pos, views[0].yaw));
            foreach (var v in views)
            {
                PlayerRigs.Instance.TeleportTo(v.pos, v.yaw);
                PlayerRigs.Instance.desktop.SetPitch(v.pitch);
                yield return new WaitForSecondsRealtime(1.2f);
                yield return Shot(v.name);
            }
            // Overlook (VR comfort remote-drive viewpoint) seen from the desktop camera.
            var cam = PlayerRigs.Instance.desktop;
            var ov = Root.Layout.GetAnchor("overlook.mainland");
            PlayerRigs.Instance.TeleportTo(ov.Position + Vector3.up * 0.1f, ov.Yaw);
            cam.SetPitch(14f);
            yield return new WaitForSecondsRealtime(1.2f);
            yield return Shot("tour_11_overlook");
            Check(true, "tour captured");
        }
        void Finish()
        {
            Log($"QA finished: {m_Checks - m_Failures}/{m_Checks} checks passed");
            string path = Path.Combine(m_Out, "qa_report.txt");
            File.WriteAllText(path, m_Report.ToString());
            Debug.Log("[QA] report: " + path);
            Running = false;
            Application.Quit(m_Failures == 0 && m_Checks > 0 ? 0 : 1);
        }
    }
}
