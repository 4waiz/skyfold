using System;
using System.Collections;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Changes scale between the Atelier (architect) and the street. Saves a checkpoint, fades,
    /// moves the active rig to a validated anchor, switches input context, fades back in.
    /// The camera is never zoomed or flown.
    /// </summary>
    public sealed class FoldController : MonoBehaviour
    {
        public static FoldController Instance { get; private set; }

        public Transform atelierAnchor;
        public FoldStation[] stations;
        public float fadeOut = 0.22f, fadeIn = 0.35f;

        public bool InAtelier { get; private set; } = true;
        public bool InStreet => !InAtelier;
        public bool Busy { get; private set; }
        public FoldStation ReturnStation { get; set; }
        public FoldStation StationInRange { get; private set; }
        public bool Allowed { get; set; } = true;
        public int FoldCount { get; private set; }

        public event Action<bool> ScaleChanged; // true = now in the Atelier

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public FoldStation Station(string id)
        {
            foreach (var s in stations) if (s != null && s.stationId == id) return s;
            return stations != null && stations.Length > 0 ? stations[0] : null;
        }

        void Update()
        {
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            if (rigs == null || input == null) return;

            StationInRange = null;
            if (InStreet && !rigs.IsDriving)
            {
                Vector3 feet = rigs.FeetPosition;
                foreach (var s in stations)
                {
                    if (s == null) continue;
                    Vector3 d = s.transform.position - feet; d.y = 0f;
                    bool near = d.magnitude <= s.radius;
                    s.PlayerInRange = near;
                    if (near) StationInRange = s;
                }
            }
            else if (stations != null)
            {
                foreach (var s in stations) if (s != null) s.PlayerInRange = false;
            }

            var ctx = input.Context;
            if (Busy || !Allowed) return;
            if (ctx != InputContext.OnFoot && ctx != InputContext.Architect) return;
            if (!input.FoldPressedThisFrame()) return;

            if (InAtelier) StartCoroutine(Unfold());
            else if (StationInRange != null) StartCoroutine(FoldUp(StationInRange));
            else HUDMessages.Toast("Fold Stations are the kiosks with a glowing teal ring. Walk up to one to fold.");
        }

        public IEnumerator FoldUp(FoldStation station)
        {
            if (Busy) yield break;
            Busy = true;
            ReturnStation = station;
            MissionDirector.Instance?.CaptureCheckpoint("fold");
            CarryRelease();
            AudioDirector.Instance?.Play2D("fold_in", 0.9f);
            yield return ScreenFader.Instance.FadeOut(fadeOut);
            PlayerRigs.Instance.TeleportTo(atelierAnchor.position, atelierAnchor.eulerAngles.y);
            InAtelier = true;
            FoldCount++;
            ApplyContext();
            yield return null;
            yield return ScreenFader.Instance.FadeIn(fadeIn);
            Busy = false;
            ScaleChanged?.Invoke(true);
        }

        public IEnumerator Unfold()
        {
            if (Busy) yield break;
            Busy = true;
            TabletopController.Instance?.ForceDrop();
            MissionDirector.Instance?.CaptureCheckpoint("unfold");
            var station = ReturnStation != null ? ReturnStation : Station("kiosk.A");
            AudioDirector.Instance?.Play2D("fold_out", 0.9f);
            yield return ScreenFader.Instance.FadeOut(fadeOut);
            var anchor = station.arriveAnchor != null ? station.arriveAnchor : station.transform;
            PlayerRigs.Instance.TeleportTo(SafeFeet(anchor.position), anchor.eulerAngles.y);
            InAtelier = false;
            FoldCount++;
            ApplyContext();
            yield return null;
            yield return ScreenFader.Instance.FadeIn(fadeIn);
            Busy = false;
            ScaleChanged?.Invoke(false);
        }

        /// <summary>Places the player without a transition (mission start, retry, menu).</summary>
        public void SetLocationImmediate(bool atelier, FoldStation station, Anchor? streetSpot = null)
        {
            TabletopController.Instance?.ForceDrop();
            InAtelier = atelier;
            if (station != null) ReturnStation = station;
            if (atelier) PlayerRigs.Instance.TeleportTo(atelierAnchor.position, atelierAnchor.eulerAngles.y);
            else
            {
                var a = streetSpot ?? new Anchor(ReturnStation.arriveAnchor.position, ReturnStation.arriveAnchor.eulerAngles.y);
                PlayerRigs.Instance.TeleportTo(SafeFeet(a.Position), a.Yaw);
            }
            ApplyContext();
            ScaleChanged?.Invoke(atelier);
        }

        public void ApplyContext()
        {
            var input = InputRouter.Instance;
            var rigs = PlayerRigs.Instance;
            if (input == null || rigs == null) return;
            if (rigs.IsDriving) return;
            if (GameRoot.Instance != null && !GameRoot.Instance.IsPlaying) return;
            input.SetContext(InAtelier ? InputContext.Architect : InputContext.OnFoot);
            // The VR rig keeps its own context (locomotion, grab layers, controller managers); without this a
            // mission started from a menu left the player in VR unable to move or grab.
            if (rigs.Mode == PlayMode.VR && rigs.vr != null) rigs.vr.SetContext(input.Context);
            if (rigs.Mode == PlayMode.Desktop && rigs.desktop != null)
                rigs.desktop.SetView(InAtelier ? DesktopView.Architect : DesktopView.FirstPerson);
            AudioDirector.Instance?.SetMusic(InAtelier ? "music_architect_loop" : "music_street_loop");
            AudioDirector.Instance?.SetAmbience(InAtelier ? "amb_atelier_loop" : "amb_city_loop");
        }

        /// <summary>Makes sure the arrival point is clear of geometry; nudges outward if needed.</summary>
        static Vector3 SafeFeet(Vector3 feet)
        {
            const float radius = 0.3f;
            int mask = ~LayerMask.GetMask("Trigger", "MiniCity", "PlayerBody", "WorldUI");
            for (int i = 0; i < 8; i++)
            {
                Vector3 p = feet + Quaternion.Euler(0f, i * 45f, 0f) * Vector3.forward * (i == 0 ? 0f : 0.8f);
                if (!Physics.CheckCapsule(p + Vector3.up * (radius + 0.05f), p + Vector3.up * 1.6f, radius, mask, QueryTriggerInteraction.Ignore))
                    return p;
            }
            return feet;
        }

        static void CarryRelease()
        {
            var cell = PowerCell.Instance;
            if (cell != null && cell.Location == CellLocation.Held) cell.DropAtFeet();
        }
    }
}
