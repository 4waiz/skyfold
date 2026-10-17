using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    public enum MissionState { Idle, Active, Failed, Success, Results }

    /// <summary>
    /// Runs one mission: objectives in order, the storm timer, escalating hints, checkpoints,
    /// failure/retry, success and recorded results. Completion is always read from game state.
    ///
    /// Start: the mission is configured from its definition (and the campaign route if it carries one).
    /// Complete: every objective predicate returned true in order.
    /// Fail: the storm timer reached zero (nothing else fails a run; lost items respawn).
    /// Checkpoint: captured when an objective flagged Checkpoint begins and on every fold.
    /// Retry: restores the last checkpoint with at least 75 seconds on the clock.
    /// Restart: reconfigures the mission from scratch.
    /// </summary>
    public sealed class MissionDirector : MonoBehaviour
    {
        public static MissionDirector Instance { get; private set; }

        public MissionContext Ctx { get; set; }
        public MissionDefinition Current { get; private set; }
        public MissionState State { get; private set; } = MissionState.Idle;
        public int ObjectiveIndex => m_Index;
        public ObjectiveDef CurrentObjective => Current != null && m_Index >= 0 && m_Index < Current.Objectives.Count ? Current.Objectives[m_Index] : null;
        public float StormLeft { get; private set; }
        public float StormTotal { get; private set; }
        public float ObjectiveElapsed { get; private set; }
        public float PlayTime { get; private set; }
        public int HintsShown { get; private set; }
        public int Retries { get; private set; }
        public string CurrentHint { get; private set; }
        public MissionResult LastResult { get; private set; }
        public bool IntroPlaying => m_IntroPending;

        public event Action<MissionState> StateChanged;
        public event Action<ObjectiveDef, int> ObjectiveChanged;
        public event Action<ObjectiveDef> ObjectiveCompleted;
        public event Action<string> HintShown;

        int m_Index = -1;
        int m_HintLevel;
        bool m_IntroPending;
        bool m_Warned120, m_Warned30;
        float m_SuccessDelay;
        Checkpoint m_Checkpoint;
        Vector3 m_CarRespawnPos;
        float m_CarRespawnYaw;
        List<Vector2Int> m_GuideCells;
        bool m_Respawning;

        sealed class Checkpoint
        {
            public CityState.Snapshot City;
            public int Objective;
            public float Storm;
            public float Play;
            public bool Atelier;
            public string ReturnStation;
            public Vector3 PlayerPos;
            public float PlayerYaw;
            public Vector3 CarPos;
            public float CarYaw;
            public CellLocation Cell;
            public bool ConvoyDeparted, ConvoyArrived;
            public string Reason;
        }

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public bool StormHeld
        {
            get
            {
                if (State != MissionState.Active) return true;
                if (m_IntroPending) return true;
                if (Ctx.Fold != null && Ctx.Fold.Busy) return true;
                var cur = CurrentObjective;
                return cur != null && cur.PausesStorm && SettingsStore.Current.guidance == Guidance.FullTutorial;
            }
        }

        void SetState(MissionState s)
        {
            State = s;
            StateChanged?.Invoke(s);
        }

        // ------------------------------------------------------------------ begin
        public void Begin(MissionDefinition def)
        {
            Current = def;
            StopAllCoroutines();
            m_Respawning = false;
            Ctx.Dialogue.Stop();
            AudioDirector.Instance?.StopAllWorld();
            Ctx.Tabletop.ForceDrop();

            var presets = new Dictionary<string, Placement>(def.Presets);
            if (def.UseCampaignRoute) AddCampaignRoute(def, presets);

            FullScaleSlot.SuppressAnimation = true;
            Ctx.City.Configure(def.ActiveSockets, presets, def.Inventory);
            foreach (var f in def.InitialFlags) Ctx.City.SetFlag(f, true);
            FullScaleSlot.SuppressAnimation = false;

            ResetWorld(def);

            StormTotal = def.StormSeconds;
            StormLeft = StormTotal;
            PlayTime = 0f;
            HintsShown = 0;
            Retries = 0;
            m_Warned120 = m_Warned30 = false;
            m_Index = -1;
            CurrentHint = null;
            LastResult = null;

            PlacePlayer(def);
            SetState(MissionState.Active);

            m_IntroPending = def.IntroVoice != null && def.IntroVoice.Length > 0;
            foreach (var line in def.IntroVoice) Ctx.Dialogue.Play(line);

            Advance();
            CaptureCheckpoint("start");
            Debug.Log($"[SKYFOLD] Mission begin: {def.Id} ({def.Title}), storm {def.StormSeconds:0}s, guidance {SettingsStore.Current.guidance}");
        }

        void AddCampaignRoute(MissionDefinition def, Dictionary<string, Placement> presets)
        {
            var active = new HashSet<string>(def.ActiveSockets);
            bool any = false;
            foreach (var sp in ProgressStore.Campaign.placements)
            {
                if (string.IsNullOrEmpty(sp.socket)) continue;
                presets[sp.socket] = new Placement { PieceId = sp.piece, Type = sp.type, Rotation = sp.rotation, Locked = !active.Contains(sp.socket) };
                any = true;
            }
            if (!any)
            {
                // No saved route (episode chosen directly): the west causeway is standing.
                presets["bridge_west"] = new Placement { PieceId = "piece.bridge", Type = ModuleType.Bridge, Rotation = 0, Locked = !active.Contains("bridge_west") };
            }
            // A locked placement must not use a piece the player holds in this mission.
            var owned = new HashSet<string>();
            foreach (var p in def.Inventory) owned.Add(p.Id);
            var keys = new List<string>(presets.Keys);
            foreach (var k in keys)
            {
                var p = presets[k];
                if (p.Locked && owned.Contains(p.PieceId)) { p.PieceId = "fixed." + k; presets[k] = p; }
                if (!p.Locked && !owned.Contains(p.PieceId)) { p.Locked = true; p.PieceId = "fixed." + k; presets[k] = p; }
            }
        }

        void ResetWorld(MissionDefinition def)
        {
            var layout = Ctx.Layout;
            var depot = layout.GetAnchor("depot.car");
            Ctx.Car.ResetTo(depot.Position, depot.Yaw);
            m_CarRespawnPos = depot.Position;
            m_CarRespawnYaw = depot.Yaw;
            Ctx.Car.cradle?.ResetSocket(true);
            Ctx.Cell.dock?.ResetSocket(true);
            if (Ctx.Substation != null && Ctx.Substation.socket != null) Ctx.Substation.socket.ResetSocket(true);

            if (Ctx.City.GetFlag(Flags.SubstationPowered) && Ctx.Substation != null) Ctx.Cell.InsertSilently(Ctx.Substation.socket);
            else if (def.CellInCradleAtStart) Ctx.Cell.InsertSilently(Ctx.Car.cradle);
            else Ctx.Cell.ResetToDock();
            if (Ctx.Substation != null) Ctx.Substation.socket.lockWhenFilled = true;
            if (Ctx.City.GetFlag(Flags.SubstationPowered) && Ctx.Substation != null) Ctx.Substation.socket.allowRemove = false;

            Ctx.Beacons.Configure(def.IsDemo);
            if (def.ConvoyAtTerminal) Ctx.Convoy.PlaceAtTerminal();
            else Ctx.Convoy.ResetAtDepot();
            Ctx.Aircraft.ResetToPark();
            FindAnyObjectByType<TrafficDirector>()?.ResetCars();
            StormDirector.Instance?.SetProgress(0f);
            Ctx.Guide.Hide();
            Ctx.Tabletop.SyncFromState();
            Ctx.Nuri.SnapToPlayer();
        }

        void PlacePlayer(MissionDefinition def)
        {
            var fold = Ctx.Fold;
            var layout = Ctx.Layout;
            switch (def.Start)
            {
                case StartLocation.Atelier:
                    fold.SetLocationImmediate(true, fold.Station(def.ReturnKiosk));
                    break;
                case StartLocation.StreetDepot:
                    fold.SetLocationImmediate(false, fold.Station("kiosk.A"), layout.GetAnchor("start.street.A"));
                    break;
                case StartLocation.StreetAirfield:
                    fold.SetLocationImmediate(false, fold.Station("kiosk.B"), layout.GetAnchor("start.street.B"));
                    break;
                case StartLocation.Substation:
                    fold.SetLocationImmediate(false, fold.Station("kiosk.B"), layout.GetAnchor("start.substation"));
                    break;
            }
            Ctx.Nuri.SnapToPlayer();
        }

        // ------------------------------------------------------------------ objectives
        void Advance()
        {
            m_Index++;
            ObjectiveElapsed = 0f;
            m_HintLevel = 0;
            CurrentHint = null;
            if (m_Index >= Current.Objectives.Count)
            {
                Succeed();
                return;
            }
            var o = Current.Objectives[m_Index];
            if (o.Checkpoint && m_Index > 0) CaptureCheckpoint(o.Id);
            o.OnBegin?.Invoke(Ctx);

            bool alreadyDone = SafeComplete(o);
            if (!alreadyDone)
            {
                var g = SettingsStore.Current.guidance;
                bool tutorialStep = o.PausesStorm;
                bool speak = !tutorialStep || g == Guidance.FullTutorial;
                if (speak)
                {
                    // Tagged with the objective: dropped if the player finishes it before Noor gets there.
                    if (o.VoiceBefore != null) foreach (var v in o.VoiceBefore) Ctx.Dialogue.Play(v, o.Id, 12f);
                    if (!string.IsNullOrEmpty(o.Voice)) Ctx.Dialogue.Play(o.Voice, o.Id, 12f);
                }
                var target = Ctx.Target(o.GuideTarget);
                if (target != null) Ctx.Nuri.PointAt(target, 5f);
            }
            ObjectiveChanged?.Invoke(o, m_Index);
        }

        bool SafeComplete(ObjectiveDef o)
        {
            try { return o.IsComplete != null && o.IsComplete(Ctx); }
            catch (Exception e) { Debug.LogException(e); return false; }
        }

        void CompleteCurrent()
        {
            var o = CurrentObjective;
            if (o == null) return;
            Ctx.Dialogue.DropContext(o.Id);
            try { o.OnComplete?.Invoke(Ctx); }
            catch (Exception e) { Debug.LogException(e); }
            AudioDirector.Instance?.PlayUI("objective_complete", 0.8f);
            ObjectiveCompleted?.Invoke(o);
            Debug.Log($"[SKYFOLD] Objective complete: {o.Id} at {PlayTime:0.0}s (storm left {StormLeft:0}s)");
            Advance();
        }

        void Update()
        {
            if (Current == null) return;
            float dt = Time.deltaTime;

            if (State == MissionState.Success)
            {
                m_SuccessDelay -= Time.unscaledDeltaTime;
                // Let Noor finish the closing line, but never hold the results back for long.
                if (m_SuccessDelay <= 0f && (!Ctx.Dialogue.IsSpeaking || m_SuccessDelay < -8f)) SetState(MissionState.Results);
                return;
            }
            if (State != MissionState.Active) return;

            // The storm waits for the welcome lines themselves, not for every later tutorial line.
            if (m_IntroPending && (Current.IntroVoice == null || System.Array.TrueForAll(Current.IntroVoice, v => !Ctx.Dialogue.IsPending(v))))
                m_IntroPending = false;
            PlayTime += dt;
            ObjectiveElapsed += dt;

            if (!StormHeld)
            {
                StormLeft -= dt;
                StormDirector.Instance?.SetProgress(1f - StormLeft / Mathf.Max(1f, StormTotal));
                if (!m_Warned120 && StormLeft <= 120f && StormTotal > 150f) { m_Warned120 = true; Ctx.Dialogue.Play("g.storm_warning"); AudioDirector.Instance?.PlayUI("warning_chime"); }
                if (!m_Warned30 && StormLeft <= 30f) { m_Warned30 = true; Ctx.Dialogue.PlayNow("g.storm_final"); AudioDirector.Instance?.PlayUI("warning_chime"); }
                if (StormLeft <= 0f) { StormLeft = 0f; Fail(); return; }
            }

            var o = CurrentObjective;
            if (o == null) return;
            if (SafeComplete(o)) { CompleteCurrent(); return; }
            UpdateHints(o);
        }

        void UpdateHints(ObjectiveDef o)
        {
            if (SettingsStore.Current.guidance == Guidance.Off || o.Hints == null || o.Hints.Length == 0) return;
            if (m_HintLevel >= o.Hints.Length) return;
            float due = o.HintDelay * (m_HintLevel + 1);
            if (ObjectiveElapsed < due) return;
            CurrentHint = o.Hints[m_HintLevel];
            m_HintLevel++;
            HintsShown++;
            AudioDirector.Instance?.PlayUI("hint_ping", 0.7f);
            var target = Ctx.Target(o.GuideTarget);
            if (target != null) Ctx.Nuri.PointAt(target, 6f);
            if (o.Id == "t.place" && m_HintLevel == 1 && SettingsStore.Current.guidance == Guidance.FullTutorial) Ctx.Dialogue.Play("g.hint_socket", o.Id, 8f);
            HintShown?.Invoke(CurrentHint);
        }

        /// <summary>Shows the next hint now (used by the "Hint" button on the wrist/pause panel).</summary>
        public void RequestHint()
        {
            var o = CurrentObjective;
            if (o?.Hints == null || o.Hints.Length == 0) return;
            int level = Mathf.Min(m_HintLevel, o.Hints.Length - 1);
            CurrentHint = o.Hints[level];
            m_HintLevel = Mathf.Min(m_HintLevel + 1, o.Hints.Length);
            HintsShown++;
            HintShown?.Invoke(CurrentHint);
        }

        // ------------------------------------------------------------------ checkpoints
        public void CaptureCheckpoint(string reason)
        {
            if (State != MissionState.Active || Current == null) return;
            var rigs = Ctx.Rigs;
            var cp = new Checkpoint
            {
                City = Ctx.City.Capture(),
                Objective = Mathf.Max(0, m_Index),
                Storm = StormLeft,
                Play = PlayTime,
                Atelier = Ctx.Fold.InAtelier,
                ReturnStation = Ctx.Fold.ReturnStation != null ? Ctx.Fold.ReturnStation.stationId : Current.ReturnKiosk,
                PlayerPos = rigs.IsDriving ? Ctx.Car.Position + Ctx.Car.transform.right * -2.2f : rigs.FeetPosition,
                PlayerYaw = Vector3.SignedAngle(Vector3.forward, rigs.Forward, Vector3.up),
                CarPos = Ctx.Car.Position,
                CarYaw = Ctx.Car.transform.eulerAngles.y,
                Cell = Ctx.Cell.Location,
                ConvoyDeparted = Ctx.Convoy.Departed,
                ConvoyArrived = Ctx.Convoy.Arrived,
                Reason = reason
            };
            m_Checkpoint = cp;
        }

        public void OnCarEnteredCell(Vector2Int cell)
        {
            var kind = Ctx.Layout.Kind(cell);
            if (kind != CellKind.Road && kind != CellKind.Socket && kind != CellKind.Poi) return;
            if (Ctx.Car.Position.y < 0f - 0.5f) return;
            // Respawn on the lane centre of the last good road cell, facing along the road.
            var open = Ctx.City.OpeningsAt(cell);
            Vector3 fwd = Ctx.Car.transform.forward;
            Dir best = Dir.N;
            float bestDot = -2f;
            foreach (var d in DirUtil.All)
            {
                if (!open.Has(d)) continue;
                float dot = Vector3.Dot(fwd, d.Forward());
                if (dot > bestDot) { bestDot = dot; best = d; }
            }
            m_CarRespawnPos = CityLayout.CellCenter(cell) + Vector3.up * 0.05f;
            m_CarRespawnYaw = (int)best * 90f;
        }

        /// <summary>Player asked to put the car back on the road (hold R / X while stuck).</summary>
        public void RequestCarReset()
        {
            if (m_Respawning || State != MissionState.Active || Ctx.Car == null || !Ctx.Car.HasDriver) return;
            Debug.Log($"[SKYFOLD] Car reset requested at {Ctx.Car.Position}");
            StartCoroutine(RespawnCar(false));
        }

        public void OnCarLost()
        {
            if (m_Respawning || State != MissionState.Active) return;
            StartCoroutine(RespawnCar());
        }

        IEnumerator RespawnCar(bool fromWater = true)
        {
            m_Respawning = true;
            if (Ctx.Car.HasDriver) yield return Ctx.Car.RespawnWithDriver(m_CarRespawnPos, m_CarRespawnYaw, fromWater);
            else Ctx.Car.ResetTo(m_CarRespawnPos, m_CarRespawnYaw);
            m_Respawning = false;
        }

        // ------------------------------------------------------------------ fail / retry / success
        void Fail()
        {
            if (State != MissionState.Active) return;
            SetState(MissionState.Failed);
            Ctx.Tabletop.ForceDrop();
            Ctx.Dialogue.PlayNow("g.fail");
            AudioDirector.Instance?.PlayStinger("stinger_fail");
            Ctx.Nuri.React(NuriMood.Concern);
            Debug.Log($"[SKYFOLD] Mission failed (storm) at objective {CurrentObjective?.Id} after {PlayTime:0}s");
        }

        public void Retry()
        {
            if (Current == null || m_Checkpoint == null) { Restart(); return; }
            StartCoroutine(RetryRoutine());
        }

        IEnumerator RetryRoutine()
        {
            yield return ScreenFader.Instance.FadeOut(0.25f);
            var cp = m_Checkpoint;
            Ctx.Dialogue.Stop();
            Ctx.Tabletop.ForceDrop();
            if (Ctx.Car.HasDriver) Ctx.Car.EndDriving(Ctx.Car.Position, 0f);

            FullScaleSlot.SuppressAnimation = true;
            Ctx.City.Restore(cp.City);
            FullScaleSlot.SuppressAnimation = false;

            Ctx.Car.ResetTo(cp.CarPos, cp.CarYaw);
            m_CarRespawnPos = cp.CarPos;
            m_CarRespawnYaw = cp.CarYaw;
            switch (cp.Cell)
            {
                case CellLocation.CarCradle: Ctx.Cell.InsertSilently(Ctx.Car.cradle); break;
                case CellLocation.Substation: Ctx.Cell.InsertSilently(Ctx.Substation.socket); break;
                default: Ctx.Cell.ResetToDock(); break;
            }
            if (cp.ConvoyArrived) Ctx.Convoy.PlaceAtTerminal();
            else { Ctx.Convoy.ResetAtDepot(); if (cp.ConvoyDeparted) Ctx.Convoy.Depart(); }
            Ctx.Aircraft.ResetToPark();
            Ctx.Beacons.Refresh(true);
            Ctx.Tabletop.SyncFromState();

            StormLeft = Mathf.Max(cp.Storm, 75f);
            PlayTime = cp.Play;
            m_Warned30 = StormLeft <= 30f;
            m_Warned120 = StormLeft <= 120f;
            StormDirector.Instance?.SetProgress(1f - StormLeft / Mathf.Max(1f, StormTotal));
            Retries++;

            var station = Ctx.Fold.Station(cp.ReturnStation);
            Ctx.Fold.SetLocationImmediate(cp.Atelier, station, cp.Atelier ? (Anchor?)null : new Anchor(cp.PlayerPos, cp.PlayerYaw));
            SetState(MissionState.Active);
            m_IntroPending = false;
            m_Index = cp.Objective - 1;
            Ctx.Dialogue.Play("g.retry");
            Advance();
            yield return ScreenFader.Instance.FadeIn(0.35f);
            Debug.Log($"[SKYFOLD] Retry from checkpoint '{cp.Reason}' (retries {Retries})");
        }

        public void Restart()
        {
            if (Current == null) return;
            StartCoroutine(RestartRoutine());
        }

        IEnumerator RestartRoutine()
        {
            yield return ScreenFader.Instance.FadeOut(0.25f);
            if (Ctx.Car.HasDriver) Ctx.Car.EndDriving(Ctx.Car.Position, 0f);
            // Begin() calls StopAllCoroutines(), which ends this routine at its next yield, so the fade back in
            // has to run on the fader itself or the screen stays black.
            var fader = ScreenFader.Instance;
            Begin(MissionCatalog.Get(Current.Id));
            fader.StartCoroutine(fader.FadeIn(0.35f));
        }

        /// <summary>The living title-screen city: broken causeway, traffic, no objectives or timer.</summary>
        public void PrepareShowcase()
        {
            var def = MissionCatalog.Get(MissionCatalog.Episode1);
            Current = null;
            m_Checkpoint = null;
            FullScaleSlot.SuppressAnimation = true;
            Ctx.City.Configure(def.ActiveSockets, def.Presets, def.Inventory);
            FullScaleSlot.SuppressAnimation = false;
            ResetWorld(def);
            SetState(MissionState.Idle);
        }

        public void Abort()
        {
            StopAllCoroutines();
            if (Ctx != null)
            {
                Ctx.Dialogue.Stop();
                Ctx.Tabletop.ForceDrop();
                if (Ctx.Car.HasDriver) Ctx.Car.EndDriving(Ctx.Car.Position, 0f);
                Ctx.Guide.Hide();
            }
            Current = null;
            m_Checkpoint = null;
            SetState(MissionState.Idle);
        }

        void Succeed()
        {
            if (State != MissionState.Active) return;
            var r = new MissionResult
            {
                MissionId = Current.Id,
                Success = true,
                StormSeconds = StormTotal,
                TimeLeft = StormLeft,
                ElapsedPlay = PlayTime,
                PlacementAttempts = Ctx.City.PlacementAttempts,
                Rejected = Ctx.City.RejectedAttempts,
                HintsShown = HintsShown,
                Retries = Retries
            };
            var route = Ctx.City.FindRoute("depot", "substation");
            r.RouteLength = route != null ? route.Count : 0;
            r.UsedShortcut = Ctx.City.RouteUsesSocket(route, "bridge_east");
            r.Medal = Current.MedalFor != null ? Current.MedalFor(r) : "";
            r.Score = Mathf.Max(0, Mathf.RoundToInt(r.TimeLeft * 10f) + (r.UsedShortcut && Current.Episode == 1 ? 500 : 0) - r.Rejected * 40 - r.HintsShown * 25 - r.Retries * 150);
            if (Current.IsDemo) r.Notes.Add("Demo progress is stored separately from your campaign.");
            LastResult = r;
            SaveProgress(r);
            m_SuccessDelay = 3f;
            SetState(MissionState.Success);
            AudioDirector.Instance?.PlayStinger(Current.Episode == 3 || Current.IsDemo ? "stinger_episode" : "stinger_success");
            Debug.Log($"[SKYFOLD] Mission success: {Current.Id} medal={r.Medal} timeLeft={r.TimeLeft:0} rejected={r.Rejected} hints={r.HintsShown} retries={r.Retries} shortcut={r.UsedShortcut}");
        }

        void SaveProgress(MissionResult r)
        {
            var store = Current.IsDemo ? ProgressStore.Demo : ProgressStore.Campaign;
            var rec = store.Record(Current.Id);
            rec.completed = true;
            if (MedalRank(r.Medal) > MedalRank(rec.bestMedal)) rec.bestMedal = r.Medal;
            rec.bestTimeLeft = Mathf.Max(rec.bestTimeLeft, r.TimeLeft);
            rec.bestScore = Mathf.Max(rec.bestScore, r.Score);
            if (Current.IsDemo) { ProgressStore.SaveDemo(); return; }

            store.unlockedEpisode = Mathf.Clamp(Mathf.Max(store.unlockedEpisode, Current.Episode + 1), 1, 3);
            // Carry the player's own route into later episodes.
            var keep = new List<SavedPlacement>();
            foreach (var s in Ctx.Layout.Sockets)
            {
                var p = Ctx.City.GetPlacement(s.Id);
                if (p.IsEmpty || p.PieceId == null || !p.PieceId.StartsWith("piece.")) continue;
                if (s.Id == "terminal_link") continue;
                keep.Add(new SavedPlacement { socket = s.Id, piece = p.PieceId, type = p.Type, rotation = p.Rotation });
            }
            if (keep.Count > 0) store.placements = keep;
            if (Ctx.City.GetFlag(Flags.SubstationPowered)) store.substationPowered = true;
            ProgressStore.SaveCampaign();
        }

        public static int MedalRank(string m) => m == "Gold" ? 3 : m == "Silver" ? 2 : m == "Bronze" ? 1 : 0;
    }
}
