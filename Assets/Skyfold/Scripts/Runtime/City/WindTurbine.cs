using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Spins a wind turbine's rotor about the turbine's forward axis. The axis is baked by the scene builder
    /// in the rotor parent's space, so it works the same on the full-scale city and the miniature.
    /// </summary>
    public sealed class WindTurbine : MonoBehaviour
    {
        public Transform rotor;
        public Vector3 axis = Vector3.forward;
        [Tooltip("Rotor speed in revolutions per minute.")]
        public float rpm = 12f;

        void Update()
        {
            if (rotor == null) return;
            rotor.localRotation = Quaternion.AngleAxis(rpm * 6f * Time.deltaTime, axis) * rotor.localRotation;
        }
    }
}
