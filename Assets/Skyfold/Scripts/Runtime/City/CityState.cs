using System;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    [Serializable]
    public struct Placement
    {
        public string PieceId;
        public ModuleType Type;
        public int Rotation;
        public bool Locked;

        public bool IsEmpty => Type == ModuleType.None;
        public DirMask Openings => ModuleInfo.Openings(Type, Rotation);
    }

    [Serializable]
    public sealed class PieceDef
    {
        public string Id;
        public ModuleType Type;
        public PieceDef(string id, ModuleType type) { Id = id; Type = type; }
    }

    /// <summary>
    /// The single authoritative state of the city. The full-scale world, the miniature, the UI and
    /// mission logic all read from this object and write to it only through its methods.
    /// </summary>
    public sealed class CityState
    {
        public CityLayout Layout { get; }

        readonly Dictionary<string, Placement> m_Placements = new Dictionary<string, Placement>();
        readonly HashSet<string> m_ActiveSockets = new HashSet<string>();
        readonly Dictionary<string, bool> m_Flags = new Dictionary<string, bool>();
        readonly List<PieceDef> m_Inventory = new List<PieceDef>();

        public event Action<string> SocketChanged;   // socket id
        public event Action RouteChanged;
        public event Action<string, bool> FlagChanged;
        public event Action InventoryChanged;
        public event Action Reset;

        public int PlacementAttempts { get; private set; }
        public int RejectedAttempts { get; private set; }

        public CityState(CityLayout layout) { Layout = layout; }

        public IReadOnlyList<PieceDef> Inventory => m_Inventory;
        public IEnumerable<string> ActiveSockets => m_ActiveSockets;
        public bool IsActive(string socketId) => m_ActiveSockets.Contains(socketId);

        public Placement GetPlacement(string socketId) =>
            m_Placements.TryGetValue(socketId, out var p) ? p : default;

        public string SocketOfPiece(string pieceId)
        {
            foreach (var kv in m_Placements)
                if (kv.Value.PieceId == pieceId) return kv.Key;
            return null;
        }

        public bool GetFlag(string key) => m_Flags.TryGetValue(key, out var v) && v;

        public void SetFlag(string key, bool value)
        {
            if (GetFlag(key) == value && m_Flags.ContainsKey(key)) return;
            m_Flags[key] = value;
            FlagChanged?.Invoke(key, value);
        }

        /// <summary>Opening mask of any cell given current placements (fixed road, POI or placed module).</summary>
        public DirMask OpeningsAt(Vector2Int cell)
        {
            var kind = Layout.Kind(cell);
            switch (kind)
            {
                case CellKind.Road:
                    return ModuleInfo.Openings(Layout.FixedType(cell), Layout.FixedRotation(cell));
                case CellKind.Poi:
                    return Layout.PoiAt(cell).Openings;
                case CellKind.Socket:
                    var socket = Layout.SocketAt(cell);
                    return GetPlacement(socket.Id).Openings;
                default:
                    return DirMask.None;
            }
        }

        // ------------------------------------------------------------------ setup / reset
        public void Configure(IEnumerable<string> activeSockets, IDictionary<string, Placement> presets, IEnumerable<PieceDef> inventory)
        {
            m_Placements.Clear();
            m_ActiveSockets.Clear();
            m_Flags.Clear();
            m_Inventory.Clear();
            PlacementAttempts = 0;
            RejectedAttempts = 0;

            foreach (var s in Layout.Sockets) m_Placements[s.Id] = default;
            if (activeSockets != null) foreach (var s in activeSockets) m_ActiveSockets.Add(s);
            if (presets != null) foreach (var kv in presets) m_Placements[kv.Key] = kv.Value;
            if (inventory != null) m_Inventory.AddRange(inventory);

            Reset?.Invoke();
            foreach (var s in Layout.Sockets) SocketChanged?.Invoke(s.Id);
            InventoryChanged?.Invoke();
            RouteChanged?.Invoke();
        }

        // ------------------------------------------------------------------ placements
        public PlacementCheck Check(string socketId, ModuleType type, int rotation) =>
            RouteValidator.CheckPlacement(this, socketId, type, rotation);

        /// <summary>Validates and, if accepted, places the piece. A rejected piece is never consumed.</summary>
        public PlacementCheck TryPlace(string socketId, string pieceId, ModuleType type, int rotation)
        {
            PlacementAttempts++;
            var check = Check(socketId, type, rotation);
            if (!check.Ok)
            {
                RejectedAttempts++;
                return check;
            }

            // A piece can only be in one socket.
            string previous = SocketOfPiece(pieceId);
            if (previous != null && previous != socketId)
            {
                m_Placements[previous] = default;
                SocketChanged?.Invoke(previous);
            }

            m_Placements[socketId] = new Placement { PieceId = pieceId, Type = type, Rotation = rotation & 3 };
            SocketChanged?.Invoke(socketId);
            RouteChanged?.Invoke();
            return check;
        }

        /// <summary>Removes the piece from its socket (picking it back up). Returns false if locked.</summary>
        public bool TryRemove(string socketId, out string reason)
        {
            reason = null;
            var p = GetPlacement(socketId);
            if (p.IsEmpty) return true;
            if (p.Locked)
            {
                reason = "That part of the road is already finished.";
                return false;
            }
            if (OccupancyCheck != null && !OccupancyCheck(socketId, out reason))
                return false;
            m_Placements[socketId] = default;
            SocketChanged?.Invoke(socketId);
            RouteChanged?.Invoke();
            return true;
        }

        /// <summary>Optional veto, e.g. a vehicle is parked on the module.</summary>
        public delegate bool OccupancyVeto(string socketId, out string reason);
        public OccupancyVeto OccupancyCheck;

        public int PlacedCount
        {
            get
            {
                int n = 0;
                foreach (var s in m_ActiveSockets) if (!GetPlacement(s).IsEmpty && !GetPlacement(s).Locked) n++;
                return n;
            }
        }

        // ------------------------------------------------------------------ routes
        public List<Vector2Int> FindRoute(string fromPoi, string toPoi)
        {
            var a = Layout.Poi(fromPoi);
            var b = Layout.Poi(toPoi);
            if (a == null || b == null) return null;
            return RouteValidator.FindPath(this, a.Cell, b.Cell);
        }

        public bool HasRoute(string fromPoi, string toPoi) => FindRoute(fromPoi, toPoi) != null;

        public bool RouteUsesSocket(List<Vector2Int> route, string socketId)
        {
            if (route == null) return false;
            var s = Layout.Socket(socketId);
            return s != null && route.Contains(s.Cell);
        }

        // ------------------------------------------------------------------ snapshots
        [Serializable]
        public sealed class Snapshot
        {
            public List<string> SocketIds = new List<string>();
            public List<Placement> Placements = new List<Placement>();
            public List<string> FlagKeys = new List<string>();
            public List<bool> FlagValues = new List<bool>();
            public int Attempts;
            public int Rejected;
        }

        public Snapshot Capture()
        {
            var s = new Snapshot { Attempts = PlacementAttempts, Rejected = RejectedAttempts };
            foreach (var kv in m_Placements) { s.SocketIds.Add(kv.Key); s.Placements.Add(kv.Value); }
            foreach (var kv in m_Flags) { s.FlagKeys.Add(kv.Key); s.FlagValues.Add(kv.Value); }
            return s;
        }

        public void Restore(Snapshot s)
        {
            if (s == null) return;
            m_Placements.Clear();
            for (int i = 0; i < s.SocketIds.Count; i++) m_Placements[s.SocketIds[i]] = s.Placements[i];
            var oldFlags = new Dictionary<string, bool>(m_Flags);
            m_Flags.Clear();
            for (int i = 0; i < s.FlagKeys.Count; i++) m_Flags[s.FlagKeys[i]] = s.FlagValues[i];
            PlacementAttempts = s.Attempts;
            RejectedAttempts = s.Rejected;
            foreach (var sock in Layout.Sockets) SocketChanged?.Invoke(sock.Id);
            foreach (var kv in m_Flags) FlagChanged?.Invoke(kv.Key, kv.Value);
            foreach (var kv in oldFlags) if (!m_Flags.ContainsKey(kv.Key)) FlagChanged?.Invoke(kv.Key, false);
            RouteChanged?.Invoke();
        }

        /// <summary>For tests and QA: number of subscribers on each event (detects duplicate listeners).</summary>
        public int ListenerCount =>
            (SocketChanged?.GetInvocationList().Length ?? 0) + (RouteChanged?.GetInvocationList().Length ?? 0) +
            (FlagChanged?.GetInvocationList().Length ?? 0) + (InventoryChanged?.GetInvocationList().Length ?? 0) +
            (Reset?.GetInvocationList().Length ?? 0);
    }
}
