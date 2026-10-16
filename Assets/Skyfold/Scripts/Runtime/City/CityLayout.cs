using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    public sealed class SocketDef
    {
        public string Id;
        public Vector2Int Cell;
        public bool Water;
        public string Label;
    }

    public sealed class PoiDef
    {
        public string Id;
        public Vector2Int Cell;
        public DirMask Openings;
        public string Label;
    }

    public struct Anchor
    {
        public Vector3 Position;
        public float Yaw;
        public Anchor(Vector3 p, float yaw) { Position = p; Yaw = yaw; }
        public Quaternion Rotation => Quaternion.Euler(0f, Yaw, 0f);
        public Vector3 Forward => Rotation * Vector3.forward;
    }

    public struct LotDressing
    {
        public Vector2Int Cell;
        public string Model;
        public int Rotation;
    }

    /// <summary>
    /// The authored Nacre Bay district: a 12 x 9 grid of 16 m cells. Rows 0-3 are the mainland,
    /// row 4 is the channel, rows 5-8 are the island airfield (row 8 is the runway).
    /// Both the full-scale city and the 1:160 miniature are generated from this data.
    /// </summary>
    public sealed class CityLayout
    {
        public const float CellSize = 16f;
        public const float MiniScale = 1f / 160f;
        public const float WaterLevel = -1.2f;
        public const float SeabedLevel = -4f;

        public readonly int Width = 12;
        public readonly int Height = 9;

        readonly CellKind[,] m_Kinds;
        readonly ModuleType[,] m_FixedType;
        readonly int[,] m_FixedRotation;

        public readonly List<SocketDef> Sockets = new List<SocketDef>();
        public readonly List<PoiDef> Pois = new List<PoiDef>();
        public readonly Dictionary<string, Anchor> Anchors = new Dictionary<string, Anchor>();
        public readonly List<LotDressing> Lots = new List<LotDressing>();

        readonly Dictionary<Vector2Int, SocketDef> m_SocketByCell = new Dictionary<Vector2Int, SocketDef>();
        readonly Dictionary<Vector2Int, PoiDef> m_PoiByCell = new Dictionary<Vector2Int, PoiDef>();

        CityLayout()
        {
            m_Kinds = new CellKind[Width, Height];
            m_FixedType = new ModuleType[Width, Height];
            m_FixedRotation = new int[Width, Height];
        }

        static CityLayout s_Cached;
        public static CityLayout NacreBay => s_Cached ??= Build();

        public bool InBounds(Vector2Int c) => c.x >= 0 && c.y >= 0 && c.x < Width && c.y < Height;
        public CellKind Kind(Vector2Int c) => InBounds(c) ? m_Kinds[c.x, c.y] : CellKind.Water;
        public ModuleType FixedType(Vector2Int c) => InBounds(c) ? m_FixedType[c.x, c.y] : ModuleType.None;
        public int FixedRotation(Vector2Int c) => InBounds(c) ? m_FixedRotation[c.x, c.y] : 0;
        public SocketDef SocketAt(Vector2Int c) => m_SocketByCell.TryGetValue(c, out var s) ? s : null;
        public PoiDef PoiAt(Vector2Int c) => m_PoiByCell.TryGetValue(c, out var p) ? p : null;

        public SocketDef Socket(string id)
        {
            foreach (var s in Sockets) if (s.Id == id) return s;
            return null;
        }

        public PoiDef Poi(string id)
        {
            foreach (var p in Pois) if (p.Id == id) return p;
            return null;
        }

        public bool IsWater(Vector2Int c)
        {
            var k = Kind(c);
            if (k == CellKind.Water) return true;
            if (k == CellKind.Socket) return SocketAt(c).Water;
            return false;
        }

        public bool IsLand(Vector2Int c) => InBounds(c) && !IsWater(c);

        public static Vector3 CellCenter(Vector2Int c) => new Vector3((c.x + 0.5f) * CellSize, 0f, (c.y + 0.5f) * CellSize);
        public static Vector3 CityCenter => new Vector3(12 * CellSize * 0.5f, 0f, 9 * CellSize * 0.5f);

        public static Vector2Int CellOf(Vector3 world) =>
            new Vector2Int(Mathf.FloorToInt(world.x / CellSize), Mathf.FloorToInt(world.z / CellSize));

        public Anchor GetAnchor(string id)
        {
            if (Anchors.TryGetValue(id, out var a)) return a;
            Debug.LogWarning("[SKYFOLD] Unknown anchor " + id);
            return new Anchor(CityCenter, 0f);
        }

        // ---------------------------------------------------------------------------------------
        static CityLayout Build()
        {
            var L = new CityLayout();
            for (int x = 0; x < L.Width; x++)
                for (int z = 0; z < L.Height; z++)
                    L.m_Kinds[x, z] = CellKind.Lot;

            // Channel and bay corners.
            for (int x = 0; x < L.Width; x++) L.m_Kinds[x, 4] = CellKind.Water;
            L.m_Kinds[0, 0] = CellKind.Water;
            L.m_Kinds[11, 0] = CellKind.Water;
            L.m_Kinds[0, 8] = CellKind.Water;
            L.m_Kinds[11, 8] = CellKind.Water;

            // Mainland roads.
            L.Road(2, 2, ModuleType.Corner, 0);
            L.Road(3, 2, ModuleType.Straight, 1);
            L.Road(4, 2, ModuleType.Tee, 1);
            L.Road(5, 2, ModuleType.Straight, 1);
            L.Road(6, 2, ModuleType.Tee, 1);
            L.Road(7, 2, ModuleType.Straight, 1);
            L.Road(8, 2, ModuleType.Tee, 2);
            L.Road(2, 3, ModuleType.Straight, 0);
            L.Road(6, 1, ModuleType.Straight, 0);
            L.Road(6, 0, ModuleType.End, 0);
            L.Road(9, 3, ModuleType.Corner, 3);

            // Island roads.
            L.Road(2, 5, ModuleType.Corner, 1);
            L.Road(3, 5, ModuleType.Straight, 1);
            L.Road(4, 5, ModuleType.Straight, 1);
            L.Road(5, 5, ModuleType.Straight, 1);
            L.Road(6, 5, ModuleType.Tee, 3);
            L.Road(7, 5, ModuleType.Straight, 1);
            L.Road(8, 5, ModuleType.Straight, 1);
            L.Road(9, 5, ModuleType.Tee, 1);
            L.Road(10, 5, ModuleType.Corner, 3);

            // Sockets (broken links the player repairs).
            L.AddSocket("bridge_west", 2, 4, true, "West crossing");
            L.AddSocket("bridge_east", 9, 4, true, "East crossing");
            L.AddSocket("harbour_corner", 8, 3, false, "Harbour corner");
            L.AddSocket("terminal_link", 6, 6, false, "Terminal access");

            // Points of interest (graph endpoints).
            L.AddPoi("depot", 8, 1, DirMask.N, "Courier depot");
            L.AddPoi("bus_terminal", 4, 1, DirMask.N, "Bus terminal");
            L.AddPoi("substation", 10, 6, DirMask.S, "Airfield substation");
            L.AddPoi("terminal", 6, 7, DirMask.S, "Passenger terminal");

            // Plazas, airfield.
            L.m_Kinds[5, 0] = CellKind.Plaza;
            L.m_Kinds[7, 0] = CellKind.Plaza;
            L.m_Kinds[3, 3] = CellKind.Plaza;
            for (int x = 1; x <= 10; x++) L.m_Kinds[x, 8] = CellKind.Runway;
            foreach (int x in new[] { 2, 3, 4, 5, 7, 8, 10 }) L.m_Kinds[x, 7] = CellKind.Apron;
            L.m_Kinds[0, 5] = CellKind.Shore;
            L.m_Kinds[11, 5] = CellKind.Shore;
            L.m_Kinds[0, 6] = CellKind.Shore;
            L.m_Kinds[0, 7] = CellKind.Shore;
            L.m_Kinds[11, 7] = CellKind.Shore;

            L.AddAnchors();
            L.AddLots();
            return L;
        }

        void Road(int x, int z, ModuleType t, int rot)
        {
            m_Kinds[x, z] = CellKind.Road;
            m_FixedType[x, z] = t;
            m_FixedRotation[x, z] = rot & 3;
        }

        void AddSocket(string id, int x, int z, bool water, string label)
        {
            var s = new SocketDef { Id = id, Cell = new Vector2Int(x, z), Water = water, Label = label };
            Sockets.Add(s);
            m_SocketByCell[s.Cell] = s;
            m_Kinds[x, z] = CellKind.Socket;
        }

        void AddPoi(string id, int x, int z, DirMask openings, string label)
        {
            var p = new PoiDef { Id = id, Cell = new Vector2Int(x, z), Openings = openings, Label = label };
            Pois.Add(p);
            m_PoiByCell[p.Cell] = p;
            m_Kinds[x, z] = CellKind.Poi;
        }

        void A(string id, float x, float y, float z, float yaw) => Anchors[id] = new Anchor(new Vector3(x, y, z), yaw);

        void AddAnchors()
        {
            // The Fold Atelier: a terrace on a headland south of the city, looking north over it.
            A("atelier.center", 96f, 22f, -46f, 0f);
            A("atelier.plinth", 96f, 22f, -44.9f, 0f);       // plinth base centre; top is +0.9
            A("atelier.player", 96f, 22f, -46.2f, 0f);        // standing spot south of the plinth
            A("atelier.menu", 96f, 23.35f, -43.6f, 0f);       // VR menu panel position

            // Street Fold Stations.
            A("kiosk.A", 129.0f, 0.15f, 31.0f, 45f);
            A("kiosk.A.arrive", 130.9f, 0.15f, 32.9f, 60f);
            A("kiosk.B", 88f, 0.15f, 94.6f, 180f);
            A("kiosk.B.arrive", 88f, 0.15f, 92.6f, 160f);

            // Depot.
            A("depot.car", 136f, 0.02f, 30.5f, 0f);
            A("depot.dock", 141.2f, 0.15f, 27.6f, 270f);
            A("bus.spawn", 72f, 0.02f, 22f, 0f);

            // Island.
            A("substation.socket", 168f, 1.1f, 102.3f, 180f);
            A("substation.park", 168f, 0.02f, 96.5f, 0f);
            A("substation.player", 165.2f, 0.15f, 100.6f, 120f);
            A("terminal.stop", 104f, 0.02f, 112.6f, 90f);
            A("plane.park", 88f, 0f, 121f, 270f);
            A("plane.taxi.1", 40f, 0f, 121f, 270f);
            A("plane.taxi.2", 40f, 0f, 129f, 0f);
            A("plane.runway.start", 44f, 0f, 136f, 90f);
            A("plane.liftoff", 132f, 0f, 136f, 90f);
            A("plane.exit", 420f, 140f, 210f, 70f);
            A("tower.lever", 152f, 0.15f, 112.4f, 180f);
            A("beacon.switch.1", 56f, 0.15f, 127.2f, 0f);
            A("beacon.switch.2", 120f, 0.15f, 127.2f, 0f);
            A("beacon.switch.3", 160f, 0.15f, 127.2f, 0f);
            A("demo.beacon.switch", 175.5f, 0.15f, 101.5f, 270f);

            // Comfort "Remote Drive" overlooks: fixed, elevated viewpoints.
            A("overlook.mainland", 112f, 14f, 6f, 15f);
            A("overlook.west", 30f, 14f, 50f, 40f);
            A("overlook.island", 150f, 14f, 70f, 10f);

            // Episode start spots.
            A("start.street.A", 131.2f, 0.15f, 33.4f, 70f);
            A("start.street.B", 86f, 0.15f, 93.6f, 150f);
            A("start.substation", 164.8f, 0.15f, 99.2f, 110f);
            A("respawn.cell", 141.2f, 1.0f, 27.6f, 0f);
        }

        void AddLots()
        {
            // Deterministic building dressing: (cell, model, rotation). Rotation 0 = facade faces north.
            void Lot(int x, int z, string model, int rot) => Lots.Add(new LotDressing { Cell = new Vector2Int(x, z), Model = model, Rotation = rot });

            // Row 0 waterfront (facing the Atelier to the south: rotation 2).
            Lot(1, 0, "bldg_shoprow", 2);
            Lot(2, 0, "bldg_house_a", 2);
            Lot(3, 0, "bldg_dome", 2);
            Lot(4, 0, "bldg_shoprow", 2);
            Lot(8, 0, "bldg_house_b", 2);
            Lot(9, 0, "bldg_courtyard", 2);
            Lot(10, 0, "bldg_house_a", 2);
            // Row 1 (south of the avenue: face north).
            Lot(0, 1, "bldg_house_b", 1);
            Lot(1, 1, "bldg_house_a", 0);
            Lot(2, 1, "bldg_courtyard", 0);
            Lot(3, 1, "bldg_tower", 0);
            Lot(5, 1, "bldg_shoprow", 0);
            Lot(7, 1, "bldg_house_b", 0);
            Lot(9, 1, "bldg_tower", 0);
            Lot(10, 1, "bldg_house_a", 0);
            Lot(11, 1, "bldg_courtyard", 3);
            // Row 2/3 north of the avenue (face south, rotation 2).
            Lot(0, 2, "bldg_house_a", 1);
            Lot(1, 2, "bldg_shoprow", 1);
            Lot(9, 2, "bldg_shoprow", 2);
            Lot(10, 2, "bldg_tower", 2);
            Lot(11, 2, "bldg_house_b", 3);
            Lot(0, 3, "bldg_house_b", 2);
            Lot(1, 3, "bldg_courtyard", 1);
            Lot(4, 3, "bldg_house_a", 2);
            Lot(5, 3, "bldg_dome", 2);
            Lot(6, 3, "bldg_tower", 2);
            Lot(7, 3, "bldg_shoprow", 2);
            Lot(10, 3, "bldg_house_a", 2);
            Lot(11, 3, "bldg_house_b", 2);
            // Island.
            Lot(1, 5, "bldg_house_a", 0);
            Lot(1, 6, "bldg_house_b", 0);
            Lot(2, 6, "bldg_courtyard", 2);
            Lot(3, 6, "bldg_house_b", 2);
            Lot(4, 6, "bldg_shoprow", 2);
            Lot(5, 6, "bldg_house_a", 2);
            Lot(7, 6, "bldg_house_b", 2);
            Lot(8, 6, "bldg_shoprow", 2);
            Lot(9, 6, "bldg_house_a", 2);
            Lot(11, 6, "bldg_house_b", 3);
            Lot(1, 7, "bldg_hangar", 0);
            Lot(9, 7, "bldg_tower_control", 2);
        }
    }
}
