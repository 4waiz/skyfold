using UnityEngine;

namespace Skyfold
{
    public enum NuriMood { Idle, Happy, Concern, Celebrate, Point }

    /// <summary>
    /// NURI, the mechanical falcon. A handful of articulated parts animated procedurally: hover bob,
    /// looking at the player, flying to point at a target, celebrating and showing concern.
    /// It keeps a comfortable distance from the player's face and never blocks the view.
    /// </summary>
    public sealed class NuriCompanion : MonoBehaviour
    {
        public static NuriCompanion Instance { get; private set; }

        public Transform body, head, lens, wingL, wingR, tail;
        public Renderer lensRenderer;
        public float followDistance = 0.9f;
        public float sideOffset = 0.55f;
        public float heightOffset = 0.05f;

        Transform m_PointTarget;
        float m_PointTime;
        NuriMood m_Mood = NuriMood.Idle;
        float m_MoodTime;
        Vector3 m_Vel;
        float m_Flap;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        public NuriMood Mood => m_Mood;

        Quaternion m_BodyRest = Quaternion.identity, m_HeadRest = Quaternion.identity, m_WingLRest = Quaternion.identity,
                   m_WingRRest = Quaternion.identity, m_TailRest = Quaternion.identity;
        Vector3 m_LensScale = Vector3.one;

        void Awake()
        {
            Instance = this;
            m_Block = new MaterialPropertyBlock();
            if (body != null) m_BodyRest = body.localRotation;
            if (head != null) m_HeadRest = head.localRotation;
            if (wingL != null) m_WingLRest = wingL.localRotation;
            if (wingR != null) m_WingRRest = wingR.localRotation;
            if (tail != null) m_TailRest = tail.localRotation;
            if (lens != null) m_LensScale = lens.localScale;
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void PointAt(Transform target, float seconds = 6f)
        {
            m_PointTarget = target;
            m_PointTime = seconds;
            if (target != null) Chirp("nuri_point");
        }

        public void React(NuriMood mood, Transform about = null)
        {
            m_Mood = mood;
            m_MoodTime = mood == NuriMood.Celebrate ? 2.4f : 1.4f;
            if (about != null && mood != NuriMood.Concern) { m_PointTarget = about; m_PointTime = 1.6f; }
            switch (mood)
            {
                case NuriMood.Happy: Chirp("nuri_happy"); break;
                case NuriMood.Concern: Chirp("nuri_concern"); break;
                case NuriMood.Celebrate: Chirp("nuri_celebrate"); break;
            }
        }

        public void Celebrate() => React(NuriMood.Celebrate);

        void Chirp(string id) => AudioDirector.Instance?.PlayAt(id, transform.position, 0.75f, Random.Range(0.96f, 1.06f), 1.5f);

        public void SnapToPlayer()
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null) return;
            transform.position = HomePosition(rigs);
            m_Vel = Vector3.zero;
        }

        public Transform atelierPerch;

        Vector3 HomePosition(PlayerRigs rigs)
        {
            if (atelierPerch != null && FoldController.Instance != null && FoldController.Instance.InAtelier)
                return atelierPerch.position;
            var head = rigs.Head;
            Vector3 fwd = rigs.Forward;
            Vector3 right = Vector3.Cross(Vector3.up, fwd);
            // A little further out on a flat screen, where the narrower view makes NURI look bigger.
            float scale = rigs.IsDriving ? 1.6f : (rigs.Mode == PlayMode.Desktop ? 1.45f : 1f);
            return head.position + fwd * followDistance * scale + right * sideOffset * scale + Vector3.up * heightOffset;
        }

        void LateUpdate()
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null || rigs.Head == null) return;
            float dt = Time.deltaTime;
            float t = Time.time;
            m_MoodTime -= dt;
            if (m_MoodTime <= 0f && m_Mood != NuriMood.Idle) m_Mood = NuriMood.Idle;
            m_PointTime -= dt;
            if (m_PointTime <= 0f) m_PointTarget = null;

            Vector3 home = HomePosition(rigs);
            Vector3 goal = home;
            if (m_PointTarget != null)
            {
                // Hover just above and in front of the target, but stay within a sensible range of the player.
                Vector3 tp = m_PointTarget.position + Vector3.up * 0.35f;
                Vector3 toTarget = tp - rigs.Head.position;
                bool atelier = FoldController.Instance != null && FoldController.Instance.InAtelier;
                if (atelier) tp = m_PointTarget.position + Vector3.up * 0.12f;
                float maxReach = atelier ? 1.6f : 6f;
                goal = toTarget.magnitude > maxReach ? rigs.Head.position + toTarget.normalized * maxReach : tp;
            }
            if (m_Mood == NuriMood.Celebrate) goal += new Vector3(Mathf.Cos(t * 6f), 0.15f, Mathf.Sin(t * 6f)) * 0.25f;

            // Personal-space rule: never closer than 0.45 m to the eyes.
            Vector3 fromHead = goal - rigs.Head.position;
            if (fromHead.magnitude < 0.45f) goal = rigs.Head.position + fromHead.normalized * 0.45f;

            float bob = Mathf.Sin(t * 2.1f) * 0.035f;
            transform.position = Vector3.SmoothDamp(transform.position, goal + Vector3.up * bob, ref m_Vel, m_PointTarget != null ? 0.35f : 0.55f, 6f, dt);

            Vector3 look = m_PointTarget != null ? m_PointTarget.position - transform.position : rigs.Head.position - transform.position;
            look.y *= 0.4f;
            if (look.sqrMagnitude > 0.0001f)
            {
                Quaternion want = Quaternion.LookRotation(look.normalized, Vector3.up);
                transform.rotation = Quaternion.Slerp(transform.rotation, want, 1f - Mathf.Exp(-5f * dt));
            }

            // Wings: gentle hover flaps, faster when moving or celebrating, folded when concerned.
            float speed = m_Vel.magnitude;
            float flapRate = m_Mood == NuriMood.Celebrate ? 16f : 7f + speed * 6f;
            m_Flap += dt * flapRate;
            float amp = m_Mood == NuriMood.Concern ? 8f : (m_Mood == NuriMood.Celebrate ? 38f : 18f + speed * 10f);
            float baseAngle = m_Mood == NuriMood.Concern ? -20f : 0f;
            if (wingL != null) wingL.localRotation = m_WingLRest * Quaternion.Euler(0f, 0f, baseAngle + Mathf.Sin(m_Flap) * amp);
            if (wingR != null) wingR.localRotation = m_WingRRest * Quaternion.Euler(0f, 0f, -(baseAngle + Mathf.Sin(m_Flap) * amp));
            if (tail != null) tail.localRotation = m_TailRest * Quaternion.Euler(Mathf.Sin(t * 1.3f) * 6f + speed * 8f, 0f, 0f);
            if (head != null)
            {
                float tilt = m_Mood == NuriMood.Concern ? 18f : (m_Mood == NuriMood.Happy ? Mathf.Sin(t * 10f) * 10f : Mathf.Sin(t * 0.7f) * 6f);
                head.localRotation = m_HeadRest * Quaternion.Euler(m_Mood == NuriMood.Concern ? 14f : 0f, 0f, tilt);
            }
            if (body != null && m_Mood == NuriMood.Celebrate) body.localRotation = Quaternion.Euler(0f, Mathf.Repeat(t * 540f, 360f), 0f) * m_BodyRest;
            else if (body != null) body.localRotation = Quaternion.Slerp(body.localRotation, m_BodyRest, 1f - Mathf.Exp(-8f * dt));

            if (lensRenderer != null)
            {
                Color c = m_Mood == NuriMood.Concern ? new Color(0.95f, 0.44f, 0.29f) : new Color(0.21f, 0.88f, 0.82f);
                float k = m_Mood == NuriMood.Celebrate ? 6f : (m_Mood == NuriMood.Concern ? 2.5f + Mathf.Abs(Mathf.Sin(t * 12f)) * 2f : 3f + Mathf.Sin(t * 1.7f) * 0.6f);
                lensRenderer.GetPropertyBlock(m_Block);
                m_Block.SetColor(EmissionId, c * k);
                lensRenderer.SetPropertyBlock(m_Block);
            }
            if (lens != null) lens.localScale = m_LensScale * (m_Mood == NuriMood.Happy || m_Mood == NuriMood.Celebrate ? 1.12f : (m_Mood == NuriMood.Concern ? 0.85f : 1f));
        }
    }
}
