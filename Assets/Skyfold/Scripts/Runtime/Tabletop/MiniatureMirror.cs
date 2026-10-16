using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Mirrors full-scale dynamic entities (courier car, convoy, traffic, aircraft) onto the
    /// miniature by stable ID. The miniature never simulates anything on its own.
    /// </summary>
    public sealed class MiniatureMirror : MonoBehaviour
    {
        [System.Serializable]
        public sealed class Pair
        {
            public string id;
            public Transform source;
            public Transform proxy;
            public bool yawOnly = true;
        }

        public MiniCity mini;
        public List<Pair> pairs = new List<Pair>();
        public float maxAltitudeCity = 60f;

        void LateUpdate()
        {
            if (mini == null) return;
            foreach (var p in pairs)
            {
                if (p.source == null || p.proxy == null) continue;
                bool visible = p.source.gameObject.activeInHierarchy && p.source.position.y < maxAltitudeCity;
                if (p.proxy.gameObject.activeSelf != visible) p.proxy.gameObject.SetActive(visible);
                if (!visible) continue;
                p.proxy.position = mini.CityToWorld(p.source.position);
                var rot = p.yawOnly ? Quaternion.Euler(0f, p.source.eulerAngles.y, 0f) : p.source.rotation;
                p.proxy.rotation = mini.CityToWorldRotation(rot);
            }
        }
    }
}
