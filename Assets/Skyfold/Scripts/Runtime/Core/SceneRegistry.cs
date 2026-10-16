using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Named gameplay transforms (guide targets, anchors) registered by NamedTarget components.</summary>
    public static class SceneRegistry
    {
        static readonly Dictionary<string, Transform> s_Targets = new Dictionary<string, Transform>();
        static readonly Dictionary<string, System.Func<Transform>> s_Dynamic = new Dictionary<string, System.Func<Transform>>();

        public static void Register(string name, Transform t)
        {
            if (string.IsNullOrEmpty(name) || t == null) return;
            s_Targets[name] = t;
        }

        public static void Unregister(string name, Transform t)
        {
            if (s_Targets.TryGetValue(name, out var cur) && cur == t) s_Targets.Remove(name);
        }

        /// <summary>Targets resolved on demand (e.g. "socket.nearest", "beacon.next").</summary>
        public static void RegisterDynamic(string name, System.Func<Transform> resolver) => s_Dynamic[name] = resolver;

        public static Transform Get(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (s_Dynamic.TryGetValue(name, out var f)) return f();
            return s_Targets.TryGetValue(name, out var t) && t != null ? t : null;
        }

        public static int Count => s_Targets.Count;
    }

}
