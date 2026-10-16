using System;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Compass direction on the city grid. N = +Z, E = +X (Unity axes).</summary>
    public enum Dir { N = 0, E = 1, S = 2, W = 3 }

    [Flags]
    public enum DirMask { None = 0, N = 1, E = 2, S = 4, W = 8, All = 15 }

    /// <summary>Road module kinds. Openings are defined at rotation 0 and rotate clockwise (N to E).</summary>
    public enum ModuleType { None = 0, Straight, Corner, Tee, Cross, End, Bridge }

    public enum CellKind { Lot, Road, Socket, Water, Plaza, Runway, Apron, Poi, Shore }

    public static class DirUtil
    {
        public static readonly Dir[] All = { Dir.N, Dir.E, Dir.S, Dir.W };

        public static DirMask Mask(this Dir d) => (DirMask)(1 << (int)d);
        public static Dir Opposite(this Dir d) => (Dir)(((int)d + 2) & 3);
        public static Dir Rotate(this Dir d, int quarterTurns) => (Dir)((((int)d + quarterTurns) % 4 + 4) % 4);
        public static bool Has(this DirMask m, Dir d) => (m & d.Mask()) != 0;

        public static Vector2Int Offset(this Dir d)
        {
            switch (d)
            {
                case Dir.N: return new Vector2Int(0, 1);
                case Dir.E: return new Vector2Int(1, 0);
                case Dir.S: return new Vector2Int(0, -1);
                default: return new Vector2Int(-1, 0);
            }
        }

        public static Vector3 Forward(this Dir d)
        {
            var o = d.Offset();
            return new Vector3(o.x, 0f, o.y);
        }

        public static DirMask Rotate(this DirMask m, int quarterTurns)
        {
            DirMask r = DirMask.None;
            foreach (var d in All)
                if (m.Has(d)) r |= d.Rotate(quarterTurns).Mask();
            return r;
        }

        public static int Count(this DirMask m)
        {
            int c = 0;
            foreach (var d in All) if (m.Has(d)) c++;
            return c;
        }

        public static string Name(this Dir d)
        {
            switch (d)
            {
                case Dir.N: return "north";
                case Dir.E: return "east";
                case Dir.S: return "south";
                default: return "west";
            }
        }

        /// <summary>Nearest quarter turn (0..3) for a yaw in degrees.</summary>
        public static int QuarterTurnsFromYaw(float yawDegrees)
        {
            int q = Mathf.RoundToInt(Mathf.Repeat(yawDegrees, 360f) / 90f);
            return q & 3;
        }
    }

    public static class ModuleInfo
    {
        /// <summary>Openings at rotation 0.</summary>
        public static DirMask BaseOpenings(ModuleType t)
        {
            switch (t)
            {
                case ModuleType.Straight: return DirMask.N | DirMask.S;
                case ModuleType.Corner: return DirMask.N | DirMask.E;
                case ModuleType.Tee: return DirMask.N | DirMask.E | DirMask.S;
                case ModuleType.Cross: return DirMask.All;
                case ModuleType.End: return DirMask.N;
                case ModuleType.Bridge: return DirMask.N | DirMask.S;
                default: return DirMask.None;
            }
        }

        public static DirMask Openings(ModuleType t, int rotation) => BaseOpenings(t).Rotate(rotation);

        public static bool IsWaterModule(ModuleType t) => t == ModuleType.Bridge;

        public static string DisplayName(ModuleType t)
        {
            switch (t)
            {
                case ModuleType.Straight: return "Straight road";
                case ModuleType.Corner: return "Corner road";
                case ModuleType.Tee: return "T-junction";
                case ModuleType.Cross: return "Crossroads";
                case ModuleType.End: return "Road end";
                case ModuleType.Bridge: return "Bridge span";
                default: return "Nothing";
            }
        }

        /// <summary>Model name used by both the miniature and full-scale representations.</summary>
        public static string ModelName(ModuleType t)
        {
            switch (t)
            {
                case ModuleType.Straight: return "road_straight";
                case ModuleType.Corner: return "road_corner";
                case ModuleType.Tee: return "road_tee";
                case ModuleType.Cross: return "road_cross";
                case ModuleType.End: return "road_end";
                case ModuleType.Bridge: return "bridge_span";
                default: return null;
            }
        }
    }
}
