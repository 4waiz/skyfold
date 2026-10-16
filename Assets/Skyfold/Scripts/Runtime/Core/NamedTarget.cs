using UnityEngine;

namespace Skyfold
{
    public sealed class NamedTarget : MonoBehaviour
    {
        public string targetName;

        void OnEnable() => SceneRegistry.Register(targetName, transform);
        void OnDisable() => SceneRegistry.Unregister(targetName, transform);
    }
}
