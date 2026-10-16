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

        /// <summary>Converts a cell path into a smooth world-space driving line on the right-hand lane.</summary>
        public static List<Vector3> PathToWorld(List<Vector2Int> cells, float laneOffset = 2f, float y = 0.05f)
        {
            var pts = new List<Vector3>();
            if (cells == null || cells.Count == 0) return pts;
            for (int i = 0; i < cells.Count; i++)
            {
                Vector3 c = CityLayout.CellCenter(cells[i]);
                Vector3 dirIn = i > 0 ? (CityLayout.CellCenter(cells[i]) - CityLayout.CellCenter(cells[i - 1])).normalized : Vector3.zero;
                Vector3 dirOut = i < cells.Count - 1 ? (CityLayout.CellCenter(cells[i + 1]) - c).normalized : dirIn;
                if (dirIn == Vector3.zero) dirIn = dirOut;
                Vector3 avg = (dirIn + dirOut);
                if (avg.sqrMagnitude < 0.01f) avg = dirOut;
                avg.Normalize();
                Vector3 right = Vector3.Cross(Vector3.up, avg);
                // Entry and exit points on cell edges keep the line on the road through corners.
                if (i > 0)
                {
                    Vector3 entry = c - dirIn * (CityLayout.CellSize * 0.5f) + Vector3.Cross(Vector3.up, dirIn) * laneOffset;
                    pts.Add(new Vector3(entry.x, y, entry.z));
                }
                Vector3 mid = c + right * laneOffset;
                if (Vector3.Dot(dirIn, dirOut) < 0.5f)
                {
                    // Corner: pull the midpoint toward the inside of the turn for a smooth arc.
                    Vector3 inner = c + (dirOut - dirIn) * (CityLayout.CellSize * 0.12f);
                    mid = inner + right * laneOffset;
                }
                pts.Add(new Vector3(mid.x, y, mid.z));
            }
            return pts;
        }
    }
}
