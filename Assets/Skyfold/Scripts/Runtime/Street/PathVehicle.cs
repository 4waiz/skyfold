using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// A kinematic vehicle that follows a world-space polyline (convoy shuttles, city traffic).
    /// It slows for anything ahead and never leaves the road graph.
    /// </summary>
    public sealed class PathVehicle : MonoBehaviour
    {
        public float cruiseSpeed = 7f;
        public float accel = 3f;
        public float lookAhead = 7f;
        public Transform[] wheels;
        public float wheelRadius = 0.36f;

        readonly List<Vector3> m_Path = new List<Vector3>();
        int m_Index;
        float m_Speed;
        float m_Spin;
        float m_StartDelay;
        Rigidbody m_Rb;

        public bool Moving => m_Index < m_Path.Count;
        public bool Finished => m_Path.Count > 0 && m_Index >= m_Path.Count;
        public Vector2Int Cell => CityLayout.CellOf(transform.position);
        public float Speed => m_Speed;

        void Awake()
        {
            m_Rb = GetComponent<Rigidbody>();
            if (m_Rb != null) { m_Rb.isKinematic = true; m_Rb.interpolation = RigidbodyInterpolation.Interpolate; }
        }

        public void SetPath(List<Vector3> path, float startDelay = 0f)
        {
            m_Path.Clear();
            if (path != null) m_Path.AddRange(path);
            // Start from the closest point ahead so re-paths do not reverse.
            m_Index = 0;
            float best = float.MaxValue;
            for (int i = 0; i < m_Path.Count; i++)
            {
                float d = (m_Path[i] - transform.position).sqrMagnitude;
                if (d < best) { best = d; m_Index = i; }
            }
            if (m_Index < m_Path.Count - 1)
            {
                Vector3 toNext = m_Path[m_Index] - transform.position;
                if (Vector3.Dot(toNext, transform.forward) < 0f) m_Index++;
            }
            m_StartDelay = startDelay;
        }

        public void Stop()
        {
            m_Path.Clear();
            m_Index = 0;
            m_Speed = 0f;
        }

        public void Place(Vector3 pos, float yaw)
        {
            Stop();
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            if (m_Rb != null) { m_Rb.position = pos; m_Rb.rotation = transform.rotation; }
        }

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            if (m_StartDelay > 0f) { m_StartDelay -= dt; return; }
            float target = 0f;
            if (m_Index < m_Path.Count)
            {
                Vector3 p = m_Path[m_Index];
                Vector3 to = p - transform.position; to.y = 0f;
                if (to.magnitude < 1.6f) { m_Index++; return; }
                target = cruiseSpeed;
                // Slow into corners.
                if (m_Index + 1 < m_Path.Count)
                {
                    Vector3 next = m_Path[m_Index + 1] - p; next.y = 0f;
                    if (Vector3.Angle(to, next) > 30f && to.magnitude < 8f) target = cruiseSpeed * 0.55f;
                }
                if (m_Index >= m_Path.Count - 2 && to.magnitude < 10f) target = Mathf.Min(target, to.magnitude * 0.7f + 0.8f);
                // Keep a safe gap to anything ahead (other vehicles, the courier car, the player).
                if (Physics.SphereCast(transform.position + Vector3.up * 1f + transform.forward * 2.6f, 0.9f, transform.forward, out var hit, lookAhead,
                        LayerMask.GetMask("Vehicle", "PlayerBody"), QueryTriggerInteraction.Ignore) && hit.collider.attachedRigidbody != m_Rb)
                    target = Mathf.Min(target, Mathf.Max(0f, hit.distance - 2f) * 0.8f);

                Quaternion want = Quaternion.LookRotation(to.normalized);
                Quaternion rot = Quaternion.RotateTowards(transform.rotation, want, 120f * dt * Mathf.Clamp01(m_Speed / 2f + 0.3f));
                m_Speed = Mathf.MoveTowards(m_Speed, target, accel * dt * (target < m_Speed ? 2.5f : 1f));
                Vector3 pos = transform.position + rot * Vector3.forward * m_Speed * dt;
                pos.y = p.y;
                if (m_Rb != null) { m_Rb.MovePosition(pos); m_Rb.MoveRotation(rot); }
                else transform.SetPositionAndRotation(pos, rot);
            }
            else m_Speed = 0f;

            m_Spin += m_Speed / wheelRadius * Mathf.Rad2Deg * dt;
            if (wheels != null) foreach (var w in wheels) if (w != null) w.localRotation = Quaternion.Euler(m_Spin, 0f, 0f);
        }
    }
}
