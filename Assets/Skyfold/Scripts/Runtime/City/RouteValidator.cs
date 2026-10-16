using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    public enum PlacementFailure
    {
        None,
        UnknownSocket,
        SocketInactive,
        Occupied,
        WrongTerrainNeedsBridge,
        WrongTerrainBridgeOnLand,
        FacesWater,
        FacesBuilding,
        FacesRoadSide,
        FacesEdge,
        NotConnected
    }

    public struct PlacementCheck
    {
        public bool Ok;
        public PlacementFailure Failure;
        public Dir Direction;
        public string Message;

        public static PlacementCheck Accept() => new PlacementCheck { Ok = true, Failure = PlacementFailure.None, Message = "It fits." };

        public static PlacementCheck Reject(PlacementFailure f, Dir d, string msg) =>
            new PlacementCheck { Ok = false, Failure = f, Direction = d, Message = msg };
    }

    /// <summary>
    /// Pure rules for the road graph. Evaluated only when a placement changes (never per frame).
    /// </summary>
    public static class RouteValidator
    {
        public static PlacementCheck CheckPlacement(CityState state, string socketId, ModuleType type, int rotation)
        {
            var layout = state.Layout;
            var socket = layout.Socket(socketId);
            if (socket == null)
                return PlacementCheck.Reject(PlacementFailure.UnknownSocket, Dir.N, "There's no socket there.");
            if (!state.IsActive(socketId))
                return PlacementCheck.Reject(PlacementFailure.SocketInactive, Dir.N, "That road isn't broken right now.");

            var existing = state.GetPlacement(socketId);
            if (!existing.IsEmpty && existing.Locked)
                return PlacementCheck.Reject(PlacementFailure.Occupied, Dir.N, "That part of the road is already finished.");

            if (socket.Water && !ModuleInfo.IsWaterModule(type))
                return PlacementCheck.Reject(PlacementFailure.WrongTerrainNeedsBridge, Dir.N, "Roads sink in open water. This gap needs a bridge span.");
            if (!socket.Water && ModuleInfo.IsWaterModule(type))
                return PlacementCheck.Reject(PlacementFailure.WrongTerrainBridgeOnLand, Dir.N, "A bridge span belongs over water. This gap is on land.");

            var openings = ModuleInfo.Openings(type, rotation);
            bool touchesRoad = false;

            foreach (var d in DirUtil.All)
            {
                var neighbour = socket.Cell + d.Offset();
                bool hasOpening = openings.Has(d);
                if (!hasOpening) continue;

                if (!layout.InBounds(neighbour))
                    return PlacementCheck.Reject(PlacementFailure.FacesEdge, d, $"The {d.Name()} end leads off the map. Turn it a quarter.");

                var kind = layout.Kind(neighbour);
                switch (kind)
                {
                    case CellKind.Road:
                    case CellKind.Poi:
                    {
                        var other = state.OpeningsAt(neighbour);
                        if (other.Has(d.Opposite())) { touchesRoad = true; break; }
                        return PlacementCheck.Reject(PlacementFailure.FacesRoadSide, d, $"The {d.Name()} end runs into the side of a road. Turn it a quarter.");
                    }
                    case CellKind.Socket:
                    {
                        var other = state.GetPlacement(layout.SocketAt(neighbour).Id);
                        if (other.IsEmpty) break; // an open socket is a future connection
                        if (other.Openings.Has(d.Opposite())) { touchesRoad = true; break; }
                        return PlacementCheck.Reject(PlacementFailure.FacesRoadSide, d, $"The {d.Name()} end hits the side of the piece next to it.");
                    }
                    case CellKind.Water:
                        return PlacementCheck.Reject(PlacementFailure.FacesWater, d, $"The {d.Name()} end runs into the water. Turn it a quarter.");
                    default:
                        return PlacementCheck.Reject(PlacementFailure.FacesBuilding, d, $"The {d.Name()} end points into a building. Turn it a quarter.");
                }
            }

            if (!touchesRoad)
                return PlacementCheck.Reject(PlacementFailure.NotConnected, Dir.N, "That piece isn't touching any road yet.");

            return PlacementCheck.Accept();
        }

        static bool Connected(CityState state, Vector2Int a, Dir d)
        {
            var b = a + d.Offset();
            if (!state.Layout.InBounds(b)) return false;
            return state.OpeningsAt(a).Has(d) && state.OpeningsAt(b).Has(d.Opposite());
        }

        /// <summary>Breadth-first search over connected road cells. Returns the cell path or null.</summary>
        public static List<Vector2Int> FindPath(CityState state, Vector2Int from, Vector2Int to)
        {
            if (from == to) return new List<Vector2Int> { from };
            var prev = new Dictionary<Vector2Int, Vector2Int>();
            var queue = new Queue<Vector2Int>();
            var seen = new HashSet<Vector2Int> { from };
            queue.Enqueue(from);
            while (queue.Count > 0)
            {
                var c = queue.Dequeue();
                foreach (var d in DirUtil.All)
                {
                    if (!Connected(state, c, d)) continue;
                    var n = c + d.Offset();
                    if (!seen.Add(n)) continue;
                    prev[n] = c;
                    if (n == to)
                    {
                        var path = new List<Vector2Int> { to };
                        var cur = to;
                        while (cur != from) { cur = prev[cur]; path.Add(cur); }
                        path.Reverse();
                        return path;
                    }
                    queue.Enqueue(n);
                }
            }
            return null;
        }

        /// <summary>All cells reachable from a start cell (used for ambient traffic and lighting the network).</summary>
        public static HashSet<Vector2Int> Reachable(CityState state, Vector2Int from)
        {
            var seen = new HashSet<Vector2Int> { from };
            var queue = new Queue<Vector2Int>();
            queue.Enqueue(from);
            while (queue.Count > 0)
            {
                var c = queue.Dequeue();
                foreach (var d in DirUtil.All)
                {
                    if (!Connected(state, c, d)) continue;
                    var n = c + d.Offset();
                    if (seen.Add(n)) queue.Enqueue(n);
                }
            }
            return seen;
        }

        static Vector3 RightOf(Vector3 dir) => new Vector3(dir.z, 0f, -dir.x);

        /// <summary>
        /// Converts a cell path into a world-space driving line on the right-hand lane, with
        /// quarter-circle arcs through corner cells.
        /// </summary>
        public static List<Vector3> PathToWorld(List<Vector2Int> cells, float laneOffset = 2f, float y = 0.05f)
        {
            var pts = new List<Vector3>();
            if (cells == null || cells.Count == 0) return pts;
            float half = CityLayout.CellSize * 0.5f;
            if (cells.Count == 1)
            {
                pts.Add(CityLayout.CellCenter(cells[0]) + Vector3.up * y);
                return pts;
            }

            Vector3 Dir(int i) => (CityLayout.CellCenter(cells[i + 1]) - CityLayout.CellCenter(cells[i])).normalized;

            Vector3 first = Dir(0);
            pts.Add(CityLayout.CellCenter(cells[0]) + RightOf(first) * laneOffset);

            for (int i = 1; i < cells.Count; i++)
            {
                Vector3 c = CityLayout.CellCenter(cells[i]);
                Vector3 dirIn = Dir(i - 1);
                Vector3 entry = c - dirIn * half + RightOf(dirIn) * laneOffset;
                pts.Add(entry);
                if (i == cells.Count - 1)
                {
                    pts.Add(c + RightOf(dirIn) * laneOffset);
                    break;
                }
                Vector3 dirOut = Dir(i);
                if (Vector3.Dot(dirIn, dirOut) > 0.5f) continue; // straight through
                if (Vector3.Dot(dirIn, dirOut) < -0.5f)
                {
                    // U-turn inside a dead end: go round the cell centre.
                    pts.Add(c + dirIn * (half * 0.5f));
                    continue;
                }
                Vector3 pivot = c - dirIn * half + dirOut * half;
                Vector3 exit = c + dirOut * half + RightOf(dirOut) * laneOffset;
                Vector3 a = entry - pivot;
                Vector3 b = exit - pivot;
                float radius = a.magnitude;
                for (int k = 1; k <= 3; k++)
                {
                    float t = k / 4f;
                    Vector3 v = Vector3.Slerp(a.normalized, b.normalized, t) * radius;
                    pts.Add(pivot + v);
                }
            }

            for (int i = 0; i < pts.Count; i++) pts[i] = new Vector3(pts[i].x, y, pts[i].z);
            return pts;
        }
    }
}
