using System;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Tabletop rules glue: holding, previewing, snapping and rejecting pieces. All decisions go
    /// through CityState/RouteValidator; this class only presents them (sound, light, haptics).
    /// </summary>
    public sealed class TabletopController : MonoBehaviour
    {
        public static TabletopController Instance { get; private set; }

        public MiniCity mini;
        public List<ModulePiece> pieces = new List<ModulePiece>();
        public float captureCells = 0.85f;
        public float maxHoldHeight = 0.25f;

        CityState m_City;
        ModulePiece m_Held;
        TileSocket m_Preview;
        Hand? m_HeldHand;

        public bool AnyPieceHeld => m_Held != null;
        public ModulePiece Held => m_Held;
        public int PickUps { get; private set; }
        public string LastPlacedSocket { get; private set; }
        public event Action<ModulePiece, PlacementCheck, TileSocket> PlacementResolved;
        public event Action<ModulePiece> PiecePicked;

        void Awake() => Instance = this;
        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (m_City != null) m_City.SocketChanged -= OnSocketChanged;
        }

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.SocketChanged -= OnSocketChanged;
            m_City = city;
            m_City.SocketChanged += OnSocketChanged;
        }

        public ModulePiece Piece(string id)
        {
            foreach (var p in pieces) if (p != null && p.pieceId == id) return p;
            return null;
        }

        /// <summary>Puts every piece where CityState says it is (tray or socket). Used at mission start and retry.</summary>
        public void SyncFromState()
        {
            ForceDrop();
            PickUps = 0;
            var inventory = new HashSet<string>();
            foreach (var d in m_City.Inventory) inventory.Add(d.Id);
            int slot = 0;
            foreach (var p in pieces)
            {
                if (p == null) continue;
                bool owned = inventory.Contains(p.pieceId);
                p.gameObject.SetActive(owned);
                p.HideGhost();
                if (!owned) continue;
                string socket = m_City.SocketOfPiece(p.pieceId);
                if (socket != null)
                {
                    var s = mini.Socket(socket);
                    var pl = m_City.GetPlacement(socket);
                    p.SocketId = socket;
                    p.SetImmediate(s.transform.position, mini.CityToWorldRotation(Quaternion.Euler(0f, pl.Rotation * 90f, 0f)), PieceState.Placed);
                }
                else
                {
                    p.SocketId = null;
                    var home = mini.traySlots != null && slot < mini.traySlots.Length ? mini.traySlots[slot] : mini.tray;
                    p.homeSlot = home;
                    p.SetImmediate(home.position, home.rotation, PieceState.InTray);
                }
                if (p.homeSlot == null || socket == null)
                {
                    if (mini.traySlots != null && slot < mini.traySlots.Length) p.homeSlot = mini.traySlots[slot];
                }
                slot++;
            }
            RefreshSockets();
        }

        void OnSocketChanged(string id) => RefreshSockets();

        void RefreshSockets()
        {
            if (mini == null || m_City == null) return;
            foreach (var s in mini.Sockets)
                s.SetState(m_City.IsActive(s.socketId), !m_City.GetPlacement(s.socketId).IsEmpty);
        }

        public bool BeginHold(ModulePiece p)
        {
            if (m_City == null || p == null) return false;
            if (m_Held != null && m_Held != p) return false;
            if (p.State == PieceState.Placed || !string.IsNullOrEmpty(p.SocketId))
            {
                string socket = p.SocketId;
                if (!m_City.TryRemove(socket, out string reason))
                {
                    HUDMessages.Toast(reason);
                    AudioDirector.Instance?.PlayAt("socket_reject", p.transform.position, 0.6f);
                    return false;
                }
                p.SocketId = null;
            }
            m_Held = p;
            var rigsNow = PlayerRigs.Instance;
            m_HeldHand = rigsNow != null && rigsNow.Mode == PlayMode.VR && rigsNow.vr != null && p.Grab != null ? rigsNow.vr.HandSelecting(p.Grab) : null;
            PickUps++;
            AudioDirector.Instance?.PlayAt("piece_pickup", p.transform.position, 0.8f);
            HapticFor(p, 0.25f, 0.05f);
            PiecePicked?.Invoke(p);
            return true;
        }

        void Update()
        {
            if (m_Held == null) { ClearPreview(); return; }
            var socket = mini.NearestSocket(m_Held.transform.position, m_City, captureCells, maxHoldHeight);
            if (socket != m_Preview) ClearPreview();
            m_Preview = socket;
            if (socket == null) { m_Held.HideGhost(); return; }
            int q = m_Held.CurrentQuarter;
            var check = m_City.Check(socket.socketId, m_Held.type, q);
            socket.ShowPreview(check.Ok);
            m_Held.ShowGhost(socket.transform.position, mini.CityToWorldRotation(Quaternion.Euler(0f, q * 90f, 0f)), check.Ok);
            HUDMessages.SetHint(check.Ok ? "Let go to set it in place." : check.Message);
        }

        void ClearPreview()
        {
            if (m_Preview != null) m_Preview.ClearPreview();
            m_Preview = null;
        }

        public void Release(ModulePiece p)
        {
            if (p == null) return;
            if (p != m_Held) { ReturnHome(p); return; }
            m_Held = null;
            p.HideGhost();
            HUDMessages.SetHint(null);
            var socket = mini.NearestSocket(p.transform.position, m_City, captureCells, maxHoldHeight);
            ClearPreview();
            if (socket == null)
            {
                ReturnHome(p);
                AudioDirector.Instance?.PlayAt("piece_drop", p.transform.position, 0.6f);
                return;
            }

            int q = p.CurrentQuarter;
            var check = m_City.TryPlace(socket.socketId, p.pieceId, p.type, q);
            if (check.Ok)
            {
                p.SocketId = socket.socketId;
                LastPlacedSocket = socket.socketId;
                p.MoveTo(socket.transform.position, mini.CityToWorldRotation(Quaternion.Euler(0f, q * 90f, 0f)), PieceState.Placed, 0.18f);
                AudioDirector.Instance?.PlayAt("socket_snap", socket.transform.position, 1f);
                HapticFor(p, 0.7f, 0.12f);
                NuriCompanion.Instance?.React(NuriMood.Happy, socket.transform);
                PlacementResolved?.Invoke(p, check, socket);
                if (m_City.HasRoute("depot", "substation"))
                    AudioDirector.Instance?.PlayAt("route_complete", socket.transform.position, 0.9f);
            }
            else
            {
                socket.FlashReject();
                AudioDirector.Instance?.PlayAt("socket_reject", socket.transform.position, 0.9f);
                HapticFor(p, 0.35f, 0.08f);
                NuriCompanion.Instance?.React(NuriMood.Concern, socket.transform);
                HUDMessages.Toast(check.Message, true);
                PlacementResolved?.Invoke(p, check, socket);
                ReturnHome(p);
            }
        }

        public void ReturnHome(ModulePiece p)
        {
            if (p == null) return;
            var home = p.homeSlot != null ? p.homeSlot : mini.tray;
            p.SocketId = null;
            p.MoveTo(home.position, home.rotation, PieceState.InTray, 0.4f);
        }

        /// <summary>Drops whatever is held (folding away, pausing, restarting) without placing it.</summary>
        public void ForceDrop()
        {
            if (m_Held == null) return;
            var p = m_Held;
            m_Held = null;
            if (p.Grab != null && p.Grab.isSelected && p.Grab.interactionManager != null)
                p.Grab.interactionManager.CancelInteractableSelection((UnityEngine.XR.Interaction.Toolkit.Interactables.IXRSelectInteractable)p.Grab);
            p.EndDesktopHold();
            p.HideGhost();
            ReturnHome(p);
            ClearPreview();
            HUDMessages.SetHint(null);
        }

        void HapticFor(ModulePiece p, float amp, float dur)
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null || rigs.Mode != PlayMode.VR || rigs.vr == null || p.Grab == null) return;
            var hand = rigs.vr.HandSelecting(p.Grab) ?? m_HeldHand;
            if (hand.HasValue) rigs.vr.Haptic(hand.Value, amp, dur);
            else rigs.vr.HapticBoth(amp * 0.6f, dur);
        }
    }
}
