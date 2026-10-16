using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// The passenger convoy follows the repaired road graph from the bus terminal to the airport
    /// terminal. If the route is incomplete it drives as far as it can and waits, then continues
    /// automatically once the player repairs the link.
    /// </summary>
    public sealed class ConvoyDirector : MonoBehaviour
    {
        public static ConvoyDirector Instance { get; private set; }

        public List<PathVehicle> shuttles = new List<PathVehicle>();
        public float spacingSeconds = 2.2f;

        CityState m_City;
        bool m_Departed, m_Waiting, m_Arrived;
        Vector2Int m_TerminalCell;

        public bool Departed => m_Departed;
        public bool Arrived => m_Arrived;
        public bool Waiting => m_Waiting;

        void Awake() => Instance = this;

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (m_City != null) m_City.RouteChanged -= OnRouteChanged;
        }

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.RouteChanged -= OnRouteChanged;
            m_City = city;
            m_City.RouteChanged += OnRouteChanged;
            m_TerminalCell = city.Layout.Poi("terminal").Cell;
        }

        public void ResetAtDepot()
        {
            m_Departed = m_Waiting = m_Arrived = false;
            var a = m_City.Layout.GetAnchor("bus.spawn");
            for (int i = 0; i < shuttles.Count; i++)
                if (shuttles[i] != null) shuttles[i].Place(a.Position - a.Forward * (7.5f * i), a.Yaw);
        }

        public void PlaceAtTerminal()
        {
            m_Departed = true;
            m_Waiting = false;
            m_Arrived = true;
            var a = m_City.Layout.GetAnchor("terminal.stop");
            for (int i = 0; i < shuttles.Count; i++)
                if (shuttles[i] != null) shuttles[i].Place(a.Position - a.Forward * (7f * i), a.Yaw);
            m_City.SetFlag(Flags.ConvoyArrived, true);
        }

        public void Depart()
        {
            if (m_Departed && !m_Waiting) return;
            m_Departed = true;
            Route();
            AudioDirector.Instance?.PlayAt("convoy_beep", shuttles.Count > 0 && shuttles[0] != null ? shuttles[0].transform.position : transform.position, 0.8f);
        }

        void OnRouteChanged()
        {
            if (m_Departed && m_Waiting) Route();
        }

        void Route()
        {
            if (shuttles.Count == 0 || shuttles[0] == null) return;
            var from = shuttles[0].Cell;
            if (m_City.Layout.Kind(from) != CellKind.Road && m_City.Layout.Kind(from) != CellKind.Poi && m_City.Layout.Kind(from) != CellKind.Socket)
                from = m_City.Layout.Poi("bus_terminal").Cell;
            var cells = RouteValidator.FindPath(m_City, from, m_TerminalCell);
            m_Waiting = cells == null;
            if (cells == null)
            {
                // Drive to the reachable road cell closest to the terminal and wait there.
                var reach = RouteValidator.Reachable(m_City, from);
                Vector2Int best = from;
                float bestD = float.MaxValue;
                foreach (var c in reach)
                {
                    if (m_City.Layout.Kind(c) == CellKind.Poi) continue;
                    float d = (c - m_TerminalCell).sqrMagnitude;
                    if (d < bestD) { bestD = d; best = c; }
                }
                cells = RouteValidator.FindPath(m_City, from, best);
            }
            var world = RouteValidator.PathToWorld(cells, 2f, 0.02f);
            if (!m_Waiting)
            {
                var stop = m_City.Layout.GetAnchor("terminal.stop");
                world.Add(stop.Position);
            }
            for (int i = 0; i < shuttles.Count; i++)
                if (shuttles[i] != null) shuttles[i].SetPath(world, i * spacingSeconds);
        }

        void Update()
        {
            if (!m_Departed || m_Arrived || m_Waiting || shuttles.Count == 0 || shuttles[0] == null) return;
            if (shuttles[0].Finished)
            {
                m_Arrived = true;
                m_City.SetFlag(Flags.ConvoyArrived, true);
                AudioDirector.Instance?.PlayAt("door_chime", shuttles[0].transform.position, 1f, 1f, 8f);
            }
        }
    }
}
