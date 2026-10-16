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
            yield return new WaitForSeconds(1.5f);
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
            yield return new WaitForSeconds(0.5f);
        }

        IEnumerator DriveTo(string target, float timeout)
        {
            var car = CourierVehicle.Instance;
            var cells = Root.City.FindRoute("depot", "substation");
            var path = RouteValidator.PathToWorld(cells, 2f, 0f);
            int idx = 0;
            float t = 0f;
            var kb = Keyboard.current;
            while (t < timeout && car.DistanceTo(target) > 8f)
            {
                // Steer toward the next route point using the real W/A/D bindings.
                while (idx < path.Count - 1 && Vector3.Distance(new Vector3(path[idx].x, 0f, path[idx].z), new Vector3(car.Position.x, 0f, car.Position.z)) < 5f) idx++;
                Vector3 to = path[Mathf.Min(idx, path.Count - 1)] - car.Position;
                to.y = 0f;
                float angle = Vector3.SignedAngle(car.transform.forward, to, Vector3.up);
                var keys = new List<Key> { Key.W };
                if (angle > 6f) keys.Add(Key.D);
                else if (angle < -6f) keys.Add(Key.A);
                if (Mathf.Abs(angle) > 50f && car.Speed > 5f) keys.Remove(Key.W);
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(keys.ToArray()));
                t += Time.deltaTime;
                yield return null;
            }
            // Brake to a stop with S.
            float b = 0f;
            while (Mathf.Abs(car.Speed) > 0.3f && b < 6f)
            {
                if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState(Key.Space));
                b += Time.deltaTime;
                yield return null;
            }
            if (kb != null) InputSystem.QueueStateEvent(kb, new KeyboardState());
            Check(car.DistanceTo(target) <= 9f, $"car reached {target} ({car.DistanceTo(target):0.0} m)");
        }

        IEnumerator WalkTo(Vector3 feet, float yaw)
        {
            // Walking is tested elsewhere; here we stand where a player would after walking.
            PlayerRigs.Instance.TeleportTo(feet, yaw);
            yield return new WaitForSeconds(0.3f);
        }

        // ------------------------------------------------------------------ scenarios
        IEnumerator Smoke()
        {
            Root.ChooseDesktop();
            yield return new WaitForSeconds(1f);
            yield return Shot("01_title");
            Check(MenuController.Instance.Screen == "title", "title menu is open");
            Root.StartMission(MissionCatalog.Episode1);
            yield return new WaitForSeconds(2f);
            Check(MD.State == MissionState.Active, "episode 1 active");
            Check(FoldController.Instance.InAtelier, "starts in the Atelier");
            yield return Shot("02_atelier");
            yield return Press(Key.Escape);
            yield return new WaitForSeconds(0.5f);
            Check(Root.IsPaused, "Escape pauses");
            yield return Shot("03_pause");
            yield return Press(Key.Escape);
            yield return new WaitForSeconds(0.5f);
            Check(!Root.IsPaused, "Escape resumes");
        }

        IEnumerator Episode1(bool east)
        {
            Root.ChooseDesktop();
            yield return new WaitForSeconds(0.5f);
            Root.StartMission(MissionCatalog.Episode1);
            yield return new WaitForSeconds(1f);
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
            yield return new WaitForSeconds(2.5f);
            yield return Shot("e1_03_route");

            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective reached");
            yield return Press(Key.Q);
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 5f, "Q folds down into the street");
            yield return new WaitForSeconds(0.6f);
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
            yield return new WaitForSeconds(4f);
            yield return Shot("e1_07_results");
            var r = MD.LastResult;
            Check(r != null && r.Success, "result recorded");
            if (r != null) Log($"result medal={r.Medal} timeLeft={r.TimeLeft:0} rejected={r.Rejected} hints={r.HintsShown} shortcut={r.UsedShortcut}");
            Check(r != null && r.UsedShortcut == east, "shortcut flag matches the route built");
        }

        IEnumerator Demo()
        {
            Root.ChooseDesktop();
            yield return new WaitForSeconds(0.5f);
            Root.StartMission(MissionCatalog.Demo);
            float start = Time.realtimeSinceStartup;
            yield return new WaitForSeconds(1f);
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
            yield return new WaitForSeconds(6f);
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
            yield return new WaitForSeconds(1f);
            Check(MD.State == MissionState.Active, "episode 2 active");
            // Fast-forward the storm through the public timer path by waiting with time scale.
            SettingsStore.Current.guidance = Guidance.Off;
            Time.timeScale = 20f;
            yield return WaitUntil(() => MD.State == MissionState.Failed, 30f, "storm failure reached");
            Time.timeScale = 1f;
            yield return new WaitForSeconds(1f);
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
                yield return new WaitForSeconds(0.8f);
                if (i % 3 == 0) MD.Restart();
                yield return new WaitForSeconds(0.8f);
                Root.QuitToMenu();
                yield return new WaitForSeconds(0.4f);
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
                yield return new WaitForSeconds(1f);
                Log($"soak loop {loops}: managed heap {GC.GetTotalMemory(false) / (1024 * 1024)} MB, fps ~{1f / Mathf.Max(0.0001f, Time.smoothDeltaTime):0}");
            }
            Check(loops > 0, $"soak completed {loops} demo loops in {seconds / 60f:0} min");
            Log($"managed heap start {mem0 / (1024 * 1024)} MB end {GC.GetTotalMemory(false) / (1024 * 1024)} MB");
        }

        IEnumerator Campaign()
        {
            yield return Episode1(true);
            Root.QuitToMenu();
            yield return new WaitForSeconds(1f);
            Check(ProgressStore.Campaign.unlockedEpisode >= 2, "episode 2 unlocked");
            Check(ProgressStore.Campaign.placements.Count > 0, "route saved for later episodes");
        }

        IEnumerator Tour()
        {
            // Views for art review and the delivery report (real build, real renderer).
            Root.ChooseDesktop();
            yield return new WaitForSeconds(2.5f);
            yield return Shot("tour_01_title");
            Root.StartMission(MissionCatalog.Demo);
            yield return new WaitForSeconds(2.5f);
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
                yield return new WaitForSeconds(1.2f);
                yield return Shot(v.name);
            }
            // Overlook (VR comfort remote-drive viewpoint) seen from the desktop camera.
            var cam = PlayerRigs.Instance.desktop;
            var ov = Root.Layout.GetAnchor("overlook.mainland");
            PlayerRigs.Instance.TeleportTo(ov.Position + Vector3.up * 0.1f, ov.Yaw);
            cam.SetPitch(14f);
            yield return new WaitForSeconds(1.2f);
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
