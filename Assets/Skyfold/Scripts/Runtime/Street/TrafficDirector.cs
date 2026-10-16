using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// A few small city cars that wander the connected road network. When the player repairs a
    /// link, traffic starts using it, at full scale and on the miniature (via the mirror).
    /// </summary>
    public sealed class TrafficDirector : MonoBehaviour
    {
        public List<PathVehicle> cars = new List<PathVehicle>();
        public Vector2Int[] startCells = { new Vector2Int(3, 2), new Vector2Int(6, 1), new Vector2Int(7, 2), new Vector2Int(5, 5) };

        CityState m_City;
        readonly List<Vector2Int> m_Candidates = new List<Vector2Int>();
        System.Random m_Rng = new System.Random(7);

        public void Bind(CityState city)
        {
            m_City = city;
        }

        public void ResetCars()
        {
            m_Rng = new System.Random(7);
            for (int i = 0; i < cars.Count; i++)
            {
                if (cars[i] == null) continue;
                var c = startCells[i % startCells.Length];
                var dir = m_City.OpeningsAt(c);
                float yaw = dir.Has(Dir.E) ? 90f : dir.Has(Dir.N) ? 0f : dir.Has(Dir.W) ? 270f : 180f;
                cars[i].Place(CityLayout.CellCenter(c) + Quaternion.Euler(0f, yaw, 0f) * Vector3.right * 2f + Vector3.up * 0.02f, yaw);
                cars[i].gameObject.SetActive(true);
            }
        }

        void Update()
        {
            if (m_City == null) return;
            foreach (var car in cars)
            {
                if (car == null || !car.gameObject.activeInHierarchy) continue;
                if (car.Moving) continue;
                PickNewDestination(car);
            }
        }

        void PickNewDestination(PathVehicle car)
        {
            var from = car.Cell;
            if (!m_City.Layout.InBounds(from) || m_City.OpeningsAt(from) == DirMask.None) return;
            m_Candidates.Clear();
            foreach (var c in RouteValidator.Reachable(m_City, from))
            {
                var k = m_City.Layout.Kind(c);
                if (k == CellKind.Road && c != from && (c - from).sqrMagnitude > 4) m_Candidates.Add(c);
            }
            if (m_Candidates.Count == 0) return;
            var dest = m_Candidates[m_Rng.Next(m_Candidates.Count)];
            var cells = RouteValidator.FindPath(m_City, from, dest);
            if (cells == null) return;
            car.SetPath(RouteValidator.PathToWorld(cells, 2f, 0.02f), (float)m_Rng.NextDouble() * 2f);
        }
    }
}
