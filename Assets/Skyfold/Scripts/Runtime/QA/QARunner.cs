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
            // Bots queue real keyboard events; by default the Input System drops them while the window is
            // unfocused, so a QA run on a busy desktop would fail whenever another window took focus.
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
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
                case "perf": body = Perf(); break;
                case "fullcampaign": body = FullCampaign(); break;
                case "lookdev": body = LookDev(); break;
                case "menus": body = Menus(); break;
                case "walk": body = Walk(); break;
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
        IEnumerator DriveTo(string target, float timeout, Func<bool> done = null, bool requireTarget = true)
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
            var carBody = car.GetComponent<Rigidbody>();
            int vehicleMask = LayerMask.GetMask("Vehicle");
            while (t < timeout && car.DistanceTo(target) > 6.5f && (done == null || !done()))
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
                // Like a careful driver: slow for any vehicle in the lane ahead.
                if (Physics.SphereCast(car.Position + Vector3.up * 0.9f + car.transform.forward * 2f, 0.55f, car.transform.forward, out var ahead,
                        4f + Mathf.Abs(v) * 1.2f, vehicleMask, QueryTriggerInteraction.Ignore) && ahead.rigidbody != carBody)
                    targetV = Mathf.Min(targetV, Mathf.Max(0f, ahead.distance - 2.5f) * 0.6f);

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
            if (requireTarget) Check(car.DistanceTo(target) <= 9f, $"car reached {target} ({car.DistanceTo(target):0.0} m)");
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
            if (east)
            {
                // Stuck recovery: roll forward a little, stop, then hold R to put the car back on the road.
                yield return HoldKeys(1.2f, Key.W);
                yield return HoldKeys(1f, Key.Space);
                yield return HoldKeys(1.4f, Key.R);
                yield return new WaitForSecondsRealtime(1.2f);
                var cc = CityLayout.CellCenter(car.Cell);
                float off = new Vector2(car.Position.x - cc.x, car.Position.z - cc.z).magnitude;
                Check(car.HasDriver && !car.Busy && off < 1.5f, $"hold R puts the car back on the road ({off:0.0} m from the lane centre point)");
            }
            // Episode 1 ends as soon as the car is across the bridge the player built.
            yield return DriveTo("substation.park", 150f, () => MD.State != MissionState.Active, false);
            Check(car.CrossedBuiltBridge || MD.State != MissionState.Active, "drove across the built bridge to the island");
            yield return Shot("e1_06_island");
            yield return WaitUntil(() => MD.State == MissionState.Results || MD.State == MissionState.Success, 30f, "episode 1 success");
            yield return WaitUntil(() => MD.State == MissionState.Results && MenuController.Instance.Screen == "results", 20f, "results screen shown");
            yield return new WaitForSecondsRealtime(1.5f);
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
                if (i % 3 == 0)
                {
                    MD.Restart();
                    yield return new WaitForSecondsRealtime(1.2f);
                    float alpha = ScreenFader.Instance != null ? ScreenFader.Instance.Alpha : 0f;
                    Check(alpha < 0.05f, $"restart {i + 1}: the screen fades back in after Restart (fader alpha {alpha:0.00})");
                }
                else yield return new WaitForSecondsRealtime(0.8f);
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

        /// <summary>Episodes 1 (east), 2 and 3 back to back, with real saved progress in between.</summary>
        IEnumerator FullCampaign()
        {
            yield return Episode1(true);
            Root.QuitToMenu();
            yield return new WaitForSecondsRealtime(1f);
            Check(ProgressStore.Campaign.unlockedEpisode >= 2, "episode 2 unlocked");
            yield return Episode2();
            Root.QuitToMenu();
            yield return new WaitForSecondsRealtime(1f);
            Check(ProgressStore.Campaign.unlockedEpisode >= 3, "episode 3 unlocked");
            yield return Episode3();
            Root.QuitToMenu();
            yield return new WaitForSecondsRealtime(1f);
            int done = 0;
            foreach (var e in ProgressStore.Campaign.episodes) if (e.completed) done++;
            Check(done >= 3, $"all three episodes recorded as complete ({done})");
        }

        IEnumerator Episode2()
        {
            Root.StartMission(MissionCatalog.Episode2);
            yield return new WaitForSecondsRealtime(1.5f);
            Check(MD.State == MissionState.Active, "episode 2 active");
            Check(FoldController.Instance.InStreet, "episode 2 starts in the street at the depot");
            Check(Root.City.HasRoute("depot", "substation"), "episode 2 keeps the route built in episode 1");
            yield return Shot("e2_01_start");
            var cell = PowerCell.Instance;
            var car = CourierVehicle.Instance;
            yield return WalkTo(cell.transform.position + Vector3.back * 1.2f, 0f);
            cell.Interact(InteractorKind.Desktop);
            Check(cell.Location == CellLocation.Held, "picked up the cell");
            yield return WalkTo(car.cradle.transform.position + car.transform.forward * -1.4f, car.transform.eulerAngles.y);
            car.cradle.Interact(InteractorKind.Desktop);
            Check(cell.Location == CellLocation.CarCradle, "cell loaded into the cradle");
            yield return WalkTo(car.exitLeft.position, car.transform.eulerAngles.y + 90f);
            car.RequestEnter();
            yield return WaitUntil(() => car.HasDriver && !car.Busy, 5f, "entered the car");
            yield return DriveTo("substation.park", 120f);
            yield return Shot("e2_02_substation");
            yield return Press(Key.E);
            yield return WaitUntil(() => !car.HasDriver && !car.Busy, 5f, "E exits the stopped car");
            car.cradle.Interact(InteractorKind.Desktop);
            Check(cell.HeldOnDesktop, "took the cell from the cradle");
            var socket = Substation.Instance.socket;
            yield return WalkTo(socket.transform.position + Vector3.back * 1.5f, 0f);
            socket.Interact(InteractorKind.Desktop);
            yield return WaitUntil(() => Root.City.GetFlag(Flags.SubstationPowered), 3f, "substation powered");
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "e2.convoy", 10f, "convoy objective");
            yield return new WaitForSecondsRealtime(3f);
            yield return Shot("e2_03_convoy");
            yield return WaitUntil(() => MD.State == MissionState.Results, 40f, "episode 2 results");
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Shot("e2_04_results");
            var r = MD.LastResult;
            Check(r != null && r.Success, "episode 2 result recorded");
            if (r != null) Log($"episode 2 result medal={r.Medal} timeLeft={r.TimeLeft:0} hints={r.HintsShown}");
        }

        IEnumerator Episode3()
        {
            Root.StartMission(MissionCatalog.Episode3);
            yield return new WaitForSecondsRealtime(1.5f);
            Check(MD.State == MissionState.Active, "episode 3 active");
            Check(Root.City.GetFlag(Flags.SubstationPowered), "airfield already powered from episode 2");
            yield return Shot("e3_01_start");
            var fold = FoldController.Instance;
            var kiosk = fold.Station("kiosk.B");
            var stand = kiosk.arriveAnchor != null ? kiosk.arriveAnchor : kiosk.transform;
            yield return WalkTo(stand.position + Vector3.up * 0.05f, stand.eulerAngles.y);
            yield return WaitUntil(() => fold.StationInRange == kiosk, 3f, "standing at the airfield Fold Station");
            yield return Press(Key.Q);
            yield return WaitUntil(() => fold.InAtelier && !fold.Busy, 6f, "Q folds up to the Atelier from the airfield");
            int rejected = Root.City.RejectedAttempts;
            yield return PlacePiece("piece.link.tee", "terminal_link", 0);
            Check(Root.City.RejectedAttempts == rejected + 1, "tee into the terminal buildings rejected");
            yield return PlacePiece("piece.link.straight", "terminal_link", 0);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "e3.unfold", 10f, "terminal link repaired");
            yield return Shot("e3_02_link");
            yield return Press(Key.Q);
            yield return WaitUntil(() => fold.InStreet && !fold.Busy, 6f, "Q folds back down to the airfield");
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "e3.beacons", 10f, "beacon objective");
            var beacons = BeaconSystem.Instance;
            for (int i = 0; i < beacons.switches.Count; i++)
            {
                var sw = beacons.switches[i];
                yield return WalkTo(sw.transform.position + sw.transform.forward * 1.3f, sw.transform.eulerAngles.y + 180f);
                sw.Interact(InteractorKind.Desktop);
                yield return new WaitForSecondsRealtime(0.6f);
                Check(beacons.LitCount == i + 1, $"beacon switch {i + 1} lights its group ({beacons.LitCount}/{beacons.Total})");
            }
            yield return Shot("e3_03_beacons");
            yield return WaitUntil(() => ConvoyDirector.Instance.Arrived, 120f, "convoy reached the terminal over the repaired roads");
            yield return Shot("e3_04_convoy");
            yield return WaitUntil(() => AircraftSequence.Instance.ConditionsMet, 20f, "passengers boarded, aircraft ready");
            var tower = Root.Layout.GetAnchor("tower.lever");
            yield return WalkTo(tower.Position + new Vector3(0f, 0f, -1.2f), 0f);
            FindAnyObjectByType<DepartureLever>().Interact(InteractorKind.Desktop);
            Check(Root.City.GetFlag(Flags.DepartureCleared), "departure cleared at the tower");
            PlayerRigs.Instance.TeleportTo(new Vector3(100f, 0.15f, 120f), 250f);
            yield return WaitUntil(() => AircraftSequence.Instance.State >= AircraftState.TakeoffRoll, 45f, "taxi to the runway");
            yield return new WaitForSecondsRealtime(2.5f);
            yield return Shot("e3_05_takeoff");
            yield return WaitUntil(() => MD.State == MissionState.Results, 60f, "episode 3 results");
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Shot("e3_06_results");
            var r = MD.LastResult;
            Check(r != null && r.Success, "episode 3 result recorded");
            if (r != null) Log($"episode 3 result medal={r.Medal} timeLeft={r.TimeLeft:0} rejected={r.Rejected} hints={r.HintsShown}");
        }

        /// <summary>
        /// Look-dev probe: reproduces the Episode 1 arrival frame at kiosk A (same as e1_04_street), finds what
        /// is drawn at a given screen point, and re-shoots it with material variants to isolate shading issues.
        /// </summary>
        IEnumerator LookDev()
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(0.5f);
            Root.StartMission(MissionCatalog.Episode1);
            yield return new WaitForSecondsRealtime(1f);
            yield return PlacePiece("piece.bridge", "bridge_west", 0);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "folded down");
            yield return new WaitForSecondsRealtime(0.6f);
            yield return Shot("look_a_baseline");

            var cam = PlayerRigs.Instance.ActiveCamera;
            Log($"LOOK camera at {cam.transform.position} yaw {cam.transform.eulerAngles.y:0} pitch {cam.transform.eulerAngles.x:0} fov {cam.fieldOfView:0}");
            var ray = cam.ScreenPointToRay(new Vector3(460f / 1920f * Screen.width, (1f - 270f / 1080f) * Screen.height, 0f));
            var hits = new List<(float d, Renderer r)>();
            foreach (var r in FindObjectsByType<Renderer>())
                if (r.enabled && r.gameObject.activeInHierarchy && r.bounds.IntersectRay(ray, out float dist)) hits.Add((dist, r));
            hits.Sort((a, b) => a.d.CompareTo(b.d));
            var block = new MaterialPropertyBlock();
            Renderer target = null;
            foreach (var h in hits)
            {
                var r = h.r;
                r.GetPropertyBlock(block);
                var m = r.sharedMaterial;
                string path = r.name; for (var p = r.transform.parent; p != null; p = p.parent) path = p.name + "/" + path;
                var mf = r.GetComponent<MeshFilter>();
                Log($"LOOK hit {path} dist {h.d:0} mesh {(mf != null && mf.sharedMesh != null ? mf.sharedMesh.name : "-")} mats [{string.Join(",", System.Array.ConvertAll(r.sharedMaterials, x => x != null ? x.name + "/" + x.shader.name : "null"))}] mpbEmpty {block.isEmpty} layer {LayerMask.LayerToName(r.gameObject.layer)} scale {r.transform.lossyScale}");
                if (target == null && h.d > 50f && m != null && m.shader.name == "Skyfold/StylizedLit") target = r;
            }
            if (target != null)
            {
                var original = target.sharedMaterials;
                var inst = new Material(original[0]);
                inst.SetFloat("_Wrap", 1f);
                inst.SetColor("_ShadowTint", Color.white);
                var mats = (Material[])original.Clone();
                for (int i = 0; i < mats.Length; i++) mats[i] = inst;
                target.sharedMaterials = mats;
                yield return new WaitForSecondsRealtime(0.3f);
                yield return Shot("look_b_wrap1_tintwhite");

                var unlit = new Material(Shader.Find("Skyfold/Unlit"));
                if (unlit.HasProperty("_BaseColor")) unlit.SetColor("_BaseColor", new Color(0.96f, 0.94f, 0.9f));
                for (int i = 0; i < mats.Length; i++) mats[i] = unlit;
                target.sharedMaterials = mats;
                yield return new WaitForSecondsRealtime(0.3f);
                yield return Shot("look_c_unlit");

                target.enabled = false;
                yield return new WaitForSecondsRealtime(0.3f);
                yield return Shot("look_d_hidden");
                target.enabled = true;
                target.sharedMaterials = original;
            }
            else Log("LOOK no distant StylizedLit renderer under the probe point");
            Check(true, "look-dev probe captured");
        }

        /// <summary>Every menu screen opens and Esc backs out; settings survive a save and reload.</summary>
        IEnumerator Menus()
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(1f);
            foreach (var screen in new[] { "episodes", "controls", "comfort", "audio", "display", "credits" })
            {
                MenuController.Instance.Show(screen);
                yield return new WaitForSecondsRealtime(0.6f);
                Check(MenuController.Instance.Screen == screen, $"menu screen '{screen}' opens");
                yield return Shot("menu_" + screen);
                yield return Press(Key.Escape);
                yield return new WaitForSecondsRealtime(0.4f);
                Check(MenuController.Instance.Screen == "title", $"Esc returns from '{screen}' to the title (now '{MenuController.Instance.Screen}', window focused {Application.isFocused})");
            }
            yield return SliderChecks();

            // Screens that need an explicit choice ignore Back instead of closing every menu.
            MenuController.Instance.Show("vrfail", false);
            yield return new WaitForSecondsRealtime(0.5f);
            yield return Press(Key.Escape);
            yield return new WaitForSecondsRealtime(0.4f);
            Check(MenuController.Instance.Screen == "vrfail", $"Esc on 'VR did not start' keeps that screen (now '{MenuController.Instance.Screen}')");
            MenuController.Instance.Show("title", false);
            yield return new WaitForSecondsRealtime(0.3f);
            var s = SettingsStore.Current;
            float music = s.music;
            bool subs = s.subtitles;
            s.music = 0.37f;
            s.subtitles = !subs;
            SettingsStore.Save();
            SettingsStore.Load();
            Check(Mathf.Abs(SettingsStore.Current.music - 0.37f) < 0.001f && SettingsStore.Current.subtitles == !subs, "settings survive a save and reload");
            SettingsStore.Current.music = music;
            SettingsStore.Current.subtitles = subs;
            SettingsStore.Save();
            MenuController.Instance.Show("launcher", false);
            yield return new WaitForSecondsRealtime(0.6f);
            yield return Shot("menu_launcher");
            Check(MenuController.Instance.Screen == "launcher", "launcher (laptop or VR choice) shows");
        }

        /// <summary>
        /// Slider regression checks on the audio screen: every knob is a true circle on screen, a press on a
        /// row's label never changes the value, a press on the rail jumps there, and the mouse wheel nudges it.
        /// </summary>
        IEnumerator SliderChecks()
        {
            MenuController.Instance.Show("audio");
            yield return new WaitForSecondsRealtime(0.6f);
            var sliders = MenuController.Instance.GetComponentsInChildren<UnityEngine.UI.Slider>(false);
            Check(sliders.Length >= 5, $"audio screen shows {sliders.Length} sliders");
            bool round = sliders.Length > 0;
            var corners = new Vector3[4];
            foreach (var sl in sliders)
            {
                var knob = sl.handleRect != null ? sl.handleRect.Find("Knob") as RectTransform : null;
                if (knob == null) { round = false; continue; }
                knob.GetWorldCorners(corners);
                float kw = Vector3.Distance(corners[0], corners[3]), kh = Vector3.Distance(corners[0], corners[1]);
                if (kw <= 0f || Mathf.Abs(kw - kh) > 0.02f * Mathf.Max(kw, kh)) { round = false; Log($"knob of {sl.name} is {kw:0.0} x {kh:0.0}"); }
            }
            Check(round, "every slider knob is a true circle (width equals height on screen)");

            var es = UnityEngine.EventSystems.EventSystem.current;
            var master = sliders.Length > 0 ? sliders[0] : null;
            if (master != null && es != null)
            {
                es.SetSelectedGameObject(master.gameObject);
                yield return new WaitForSecondsRealtime(0.35f);
                yield return Shot("menu_audio_focus");

                UnityEngine.EventSystems.PointerEventData At(Vector2 screen)
                {
                    var pe = new UnityEngine.EventSystems.PointerEventData(es) { button = UnityEngine.EventSystems.PointerEventData.InputButton.Left, position = screen, pressPosition = screen };
                    pe.pointerPressRaycast = new UnityEngine.EventSystems.RaycastResult { screenPosition = screen };
                    return pe;
                }
                Vector2 ScreenOf(RectTransform rt, float u) =>
                    RectTransformUtility.WorldToScreenPoint(null, rt.TransformPoint(new Vector3(Mathf.Lerp(rt.rect.xMin, rt.rect.xMax, u), rt.rect.center.y, 0f)));

                float before = master.value;
                var label = master.transform.Find("Label") as RectTransform;
                var track = master.transform.Find("Track") as RectTransform;
                if (label != null && track != null)
                {
                    var pressLabel = At(ScreenOf(label, 0.3f));
                    master.OnPointerDown(pressLabel);
                    master.OnPointerUp(pressLabel);
                    Check(Mathf.Abs(master.value - before) < 0.001f, $"a press on the slider label keeps the value ({before:0.00} -> {master.value:0.00})");

                    var pressRail = At(ScreenOf(track, 0.25f));
                    master.OnPointerDown(pressRail);
                    master.OnPointerUp(pressRail);
                    Check(Mathf.Abs(master.value - 0.25f) < 0.04f, $"a press on the rail at 25% sets the value ({master.value:0.00})");

                    float v0 = master.value;
                    ((UnityEngine.EventSystems.IScrollHandler)master).OnScroll(new UnityEngine.EventSystems.PointerEventData(es) { scrollDelta = new Vector2(0f, 1f) });
                    Check(master.value > v0 + 0.03f, $"the mouse wheel nudges the slider up ({v0:0.00} -> {master.value:0.00})");
                }
                else Check(false, "slider row has Label and Track children");
                master.value = before;
            }
            yield return Press(Key.Escape);
            yield return new WaitForSecondsRealtime(0.4f);
            Check(MenuController.Instance.Screen == "title", "Esc returns from the slider checks to the title");
        }

        /// <summary>Desktop on-foot controls with real input: W walks, Shift slows, the mouse turns, E picks up.</summary>
        IEnumerator Walk()
        {
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(0.5f);
            Root.StartMission(MissionCatalog.Demo);
            yield return new WaitForSecondsRealtime(1f);
            yield return PlacePiece("piece.bridge", "bridge_east", 0);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "Q folds down into the street");
            yield return new WaitForSecondsRealtime(0.5f);
            var body = PlayerRigs.Instance.desktop;

            Vector3 p0 = body.FeetPosition;
            Vector3 fwd = body.transform.forward;
            yield return HoldKeys(1.5f, Key.W);
            float walked = Vector3.Dot(body.FeetPosition - p0, fwd);
            Check(walked > 3f, $"W walks forward ({walked:0.0} m in 1.5 s)");

            p0 = body.FeetPosition;
            fwd = body.transform.forward;
            yield return HoldKeys(1.5f, Key.W, Key.LeftShift);
            float slow = Vector3.Dot(body.FeetPosition - p0, fwd);
            Check(slow > 1f && slow < walked * 0.75f, $"Shift walks slowly ({slow:0.0} m in 1.5 s)");

            float yaw0 = body.transform.eulerAngles.y;
            var mouse = Mouse.current;
            if (mouse != null)
            {
                for (int i = 0; i < 20; i++)
                {
                    InputSystem.QueueStateEvent(mouse, new MouseState { delta = new Vector2(15f, 0f) });
                    yield return null;
                }
                InputSystem.QueueStateEvent(mouse, new MouseState());
                yield return null;
            }
            float turned = Mathf.Abs(Mathf.DeltaAngle(yaw0, body.transform.eulerAngles.y));
            Check(turned > 5f, $"mouse look turns the view ({turned:0} degrees, cursor {Cursor.lockState})");

            var cell = PowerCell.Instance;
            Vector3 stand = cell.transform.position + Vector3.back * 1.4f;
            Vector3 to = cell.transform.position - stand;
            yield return WalkTo(new Vector3(stand.x, body.FeetPosition.y, stand.z), Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg);
            float eye = body.cam.transform.position.y;
            body.SetPitch(Mathf.Atan2(eye - cell.transform.position.y, 1.4f) * Mathf.Rad2Deg);
            yield return new WaitForSecondsRealtime(0.4f);
            yield return Shot("walk_01_cell_prompt");
            yield return Press(Key.E);
            yield return new WaitForSecondsRealtime(0.4f);
            Check(cell.Location == CellLocation.Held, "E picks up the power cell");
            yield return Shot("walk_02_cell_held");

            // Event operator key: F5 restarts the demo from the top (campaign untouched).
            yield return Press(Key.F5);
            yield return new WaitForSecondsRealtime(2f);
            Check(MD.Current != null && MD.Current.IsDemo && MD.State == MissionState.Active && FoldController.Instance.InAtelier &&
                  MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.grab", "F5 operator reset restarts the demo in the Atelier");
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
            OverlookDirector.Instance?.Preview("overlook.mainland");
            PlayerRigs.Instance.TeleportTo(ov.Position + Vector3.up * 0.1f, ov.Yaw);
            cam.SetPitch(14f);
            yield return new WaitForSecondsRealtime(1.2f);
            yield return Shot("tour_11_overlook");
            Check(true, "tour captured");
        }
        // ------------------------------------------------------------------ performance
        /// <summary>Frame-time statistics over a window (uncapped: vsync is turned off for perf runs).</summary>
        IEnumerator Measure(string label, float seconds)
        {
            var frames = new List<float>();
            float t = 0f;
            long gc0 = GC.CollectionCount(0);
            while (t < seconds)
            {
                yield return null;
                float dt = Time.unscaledDeltaTime;
                frames.Add(dt);
                t += dt;
            }
            frames.Sort();
            float sum = 0f;
            foreach (var f in frames) sum += f;
            float avg = sum / frames.Count;
            float p99 = frames[Mathf.Min(frames.Count - 1, (int)(frames.Count * 0.99f))];
            float max = frames[frames.Count - 1];
            Log($"PERF {label}: {frames.Count} frames in {t:0.0}s, avg {1f / avg:0} fps ({avg * 1000f:0.00} ms), 1% low {1f / p99:0} fps ({p99 * 1000f:0.00} ms), worst {max * 1000f:0.0} ms, gen0 GCs {GC.CollectionCount(0) - gc0}");
        }

        IEnumerator Perf()
        {
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            Log($"PERF setup: {Screen.width}x{Screen.height} {(Screen.fullScreen ? "fullscreen" : "windowed")}, quality '{QualitySettings.names[QualitySettings.GetQualityLevel()]}', MSAA {QualitySettings.antiAliasing}, vsync off, {SystemInfo.graphicsDeviceName} ({SystemInfo.graphicsDeviceType}), {SystemInfo.processorType}");
            Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(2f);
            yield return Measure("title screen", 6f);
            Root.StartMission(MissionCatalog.Demo);
            yield return new WaitForSecondsRealtime(2f);
            yield return Measure("Atelier with the miniature city", 6f);
            yield return PlacePiece("piece.bridge", "bridge_east", 0);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "folded");
            var cell = PowerCell.Instance;
            var car = CourierVehicle.Instance;
            PlayerRigs.Instance.TeleportTo(new Vector3(52f, 0.15f, 30f), 70f);
            yield return new WaitForSecondsRealtime(1f);
            yield return Measure("street: avenue towards the depot", 6f);
            PlayerRigs.Instance.TeleportTo(new Vector3(118f, 0.15f, 112f), 300f);
            yield return new WaitForSecondsRealtime(1f);
            yield return Measure("street: airfield and runway", 6f);
            yield return WalkTo(cell.transform.position + Vector3.back * 1.2f, 0f);
            cell.Interact(InteractorKind.Desktop);
            yield return WalkTo(car.cradle.transform.position + car.transform.forward * -1.4f, car.transform.eulerAngles.y);
            car.cradle.Interact(InteractorKind.Desktop);
            yield return WalkTo(car.exitLeft.position, car.transform.eulerAngles.y + 90f);
            car.RequestEnter();
            yield return WaitUntil(() => car.HasDriver && !car.Busy, 5f, "entered car");
            var drive = StartCoroutine(Measure("driving across the bridge (chase camera)", 11f));
            yield return DriveTo("substation.park", 60f);
            yield return drive;
            yield return Press(Key.E);
            yield return new WaitForSecondsRealtime(1f);
            if (!car.HasDriver) car.cradle.Interact(InteractorKind.Desktop);
            var socket = Substation.Instance.socket;
            yield return WalkTo(socket.transform.position + Vector3.back * 1.5f, 0f);
            socket.Interact(InteractorKind.Desktop);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "d.beacons", 10f, "beacon objective");
            BeaconSystem.Instance.masterSwitch.Interact(InteractorKind.Desktop);
            yield return WaitUntil(() => AircraftSequence.Instance.ConditionsMet, 15f, "aircraft ready");
            var tower = Root.Layout.GetAnchor("tower.lever");
            PlayerRigs.Instance.TeleportTo(tower.Position + new Vector3(0f, 0f, -1.2f), 0f);
            FindAnyObjectByType<DepartureLever>().Interact(InteractorKind.Desktop);
            PlayerRigs.Instance.TeleportTo(new Vector3(100f, 0.15f, 120f), 250f);
            yield return WaitUntil(() => AircraftSequence.Instance.State >= AircraftState.TakeoffRoll, 45f, "takeoff roll");
            yield return Measure("takeoff roll and climb", 8f);
            yield return WaitUntil(() => MD.State == MissionState.Results, 60f, "demo results");
            yield return Measure("results screen", 4f);
            Log($"PERF memory: managed heap {GC.GetTotalMemory(false) / (1024 * 1024)} MB, system RAM {SystemInfo.systemMemorySize} MB, VRAM {SystemInfo.graphicsMemorySize} MB");
            QualitySettings.vSyncCount = 1;
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
