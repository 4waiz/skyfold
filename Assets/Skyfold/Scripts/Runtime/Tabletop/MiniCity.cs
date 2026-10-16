using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Root of the 1:160 miniature on the plinth. A presentation/interaction proxy only: it maps
    /// city coordinates to the table and owns the mini sockets; it runs no simulation of its own.
    /// </summary>
    public sealed class MiniCity : MonoBehaviour
    {
        public static MiniCity Instance { get; private set; }
        public Transform tray;
        public Transform[] traySlots;

        readonly Dictionary<string, TileSocket> m_Sockets = new Dictionary<string, TileSocket>();

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public float Scale => transform.lossyScale.x;
        public float TableHeight => transform.position.y;

        public Vector3 CityToWorld(Vector3 city) => transform.TransformPoint(city);
        public Vector3 WorldToCity(Vector3 world) => transform.InverseTransformPoint(world);
        public Quaternion CityToWorldRotation(Quaternion r) => transform.rotation * r;

        public float YawInCity(Transform t)
        {
            var local = Quaternion.Inverse(transform.rotation) * t.rotation;
            return local.eulerAngles.y;
        }

        public void Register(TileSocket s) => m_Sockets[s.socketId] = s;
        public TileSocket Socket(string id) => m_Sockets.TryGetValue(id, out var s) ? s : null;
        public IEnumerable<TileSocket> Sockets => m_Sockets.Values;

        /// <summary>Nearest active socket within captureCells (in cell units) of a world position.</summary>
        public TileSocket NearestSocket(Vector3 worldPos, CityState state, float captureCells, float maxHeight)
        {
            Vector3 city = WorldToCity(worldPos);
            if (city.y > maxHeight / Scale) return null;
            TileSocket best = null;
            float bestD = captureCells * CityLayout.CellSize;
            foreach (var s in m_Sockets.Values)
            {
                if (!state.IsActive(s.socketId)) continue;
                Vector3 c = CityLayout.CellCenter(state.Layout.Socket(s.socketId).Cell);
                float d = Vector2.Distance(new Vector2(c.x, c.z), new Vector2(city.x, city.z));
                if (d < bestD) { bestD = d; best = s; }
            }
            return best;
        }
    }
}
