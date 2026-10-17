using UnityEngine;

namespace Skyfold
{
    /// <summary>Gentle bob and sway for things floating on the bay (buoys, moored boats).</summary>
    public sealed class FloatBob : MonoBehaviour
    {
        public float amplitude = 0.08f;
        public float period = 3.6f;
        public float tilt = 2.5f;

        Vector3 m_Base;
        Quaternion m_BaseRotation;
        float m_Phase;

        void Awake()
        {
            m_Base = transform.localPosition;
            m_BaseRotation = transform.localRotation;
            // Different phase per position so neighbours never move in lockstep.
            m_Phase = Mathf.Repeat(transform.position.x * 0.37f + transform.position.z * 0.21f, Mathf.PI * 2f);
        }

        void Update()
        {
            float t = Time.time * (Mathf.PI * 2f) / period + m_Phase;
            transform.localPosition = m_Base + Vector3.up * (Mathf.Sin(t) * amplitude);
            transform.localRotation = m_BaseRotation * Quaternion.Euler(Mathf.Sin(t * 0.83f + 1.3f) * tilt, 0f, Mathf.Cos(t * 0.71f) * tilt);
        }
    }
}
