using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// A broken link on the miniature. Shows a pulsing teal ring while it can take a piece, a ✓/✕
    /// preview while a piece hovers, and a short coral flash with ✕ when a placement is rejected.
    /// </summary>
    public sealed class TileSocket : MonoBehaviour
    {
        public string socketId;
        public Renderer ring;
        public Transform iconAnchor;
        public Renderer iconValid;
        public Renderer iconInvalid;

        static readonly int ColorId = Shader.PropertyToID("_BaseColor");
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;
        float m_Flash;
        bool m_Preview, m_PreviewOk;
        bool m_Active, m_Filled;

        public static readonly Color Teal = new Color(0.21f, 0.88f, 0.82f);
        public static readonly Color Coral = new Color(0.95f, 0.44f, 0.29f);
        public static readonly Color Gold = new Color(0.85f, 0.64f, 0.25f);

        void Awake()
        {
            var mini = GetComponentInParent<MiniCity>();
            if (mini != null) mini.Register(this);
            m_Block = new MaterialPropertyBlock();
            SetIcons(false, false);
        }

        public void SetState(bool active, bool filled)
        {
            m_Active = active;
            m_Filled = filled;
        }

        public void ShowPreview(bool ok)
        {
            m_Preview = true;
            m_PreviewOk = ok;
        }

        public void ClearPreview() => m_Preview = false;

        public void FlashReject() => m_Flash = 1.2f;

        void SetIcons(bool valid, bool invalid)
        {
            if (iconValid != null && iconValid.enabled != valid) iconValid.enabled = valid;
            if (iconInvalid != null && iconInvalid.enabled != invalid) iconInvalid.enabled = invalid;
        }

        void Update()
        {
            float t = Time.time;
            m_Flash = Mathf.Max(0f, m_Flash - Time.deltaTime);
            bool showRing = m_Active && (!m_Filled || m_Preview || m_Flash > 0f);
            if (ring != null)
            {
                if (ring.enabled != showRing) ring.enabled = showRing;
                if (showRing)
                {
                    Color c = Teal;
                    float intensity = 1.2f + 0.8f * Mathf.Sin(t * 3.2f);
                    if (m_Flash > 0f) { c = Coral; intensity = 2.5f * Mathf.Abs(Mathf.Sin(m_Flash * 9f)); }
                    else if (m_Preview) { c = m_PreviewOk ? Teal : Coral; intensity = 2.4f; }
                    ring.GetPropertyBlock(m_Block);
                    m_Block.SetColor(ColorId, c);
                    m_Block.SetColor(EmissionId, c * intensity);
                    ring.SetPropertyBlock(m_Block);
                }
            }
            SetIcons(m_Preview && m_PreviewOk, (m_Preview && !m_PreviewOk) || m_Flash > 0f);
            if (iconAnchor != null)
            {
                iconAnchor.localPosition = new Vector3(0f, 6f + Mathf.Sin(t * 2.5f) * 0.6f, 0f);
                var cam = PlayerRigs.Instance != null ? PlayerRigs.Instance.ActiveCamera : Camera.main;
                if (cam != null) iconAnchor.rotation = Quaternion.LookRotation(iconAnchor.position - cam.transform.position);
            }
        }
    }
}
