using UnityEngine;

namespace Skyfold
{
    /// <summary>Keeps weather effects centred on whichever camera is active.</summary>
    public sealed class FollowActiveCamera : MonoBehaviour
    {
        public Vector3 offset;

        void LateUpdate()
        {
            var rigs = PlayerRigs.Instance;
            var cam = rigs != null ? rigs.ActiveCamera : Camera.main;
            if (cam != null) transform.position = cam.transform.position + offset;
        }
    }
}
