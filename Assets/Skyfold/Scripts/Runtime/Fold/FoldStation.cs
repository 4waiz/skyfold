using UnityEngine;

namespace Skyfold
{
    /// <summary>A street Fold Station kiosk. Its lens ring glows when the player can fold here.</summary>
    public sealed class FoldStation : MonoBehaviour
    {
        public string stationId = "kiosk.A";
        public Transform arriveAnchor;
        public Renderer lensRing;
        public float radius = 3.2f;

        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;
        float m_Glow;

        public bool PlayerInRange { get; set; }

        void Awake() => m_Block = new MaterialPropertyBlock();

        void Update()
        {
            float target = PlayerInRange ? 1f : 0.25f;
            m_Glow = Mathf.MoveTowards(m_Glow, target, Time.deltaTime * 2f);
            if (lensRing == null) return;
            lensRing.GetPropertyBlock(m_Block);
            float pulse = PlayerInRange ? 0.7f + 0.3f * Mathf.Sin(Time.time * 4f) : 1f;
            m_Block.SetColor(EmissionId, new Color(0.21f, 0.88f, 0.82f) * (0.6f + 3.2f * m_Glow * pulse));
            lensRing.SetPropertyBlock(m_Block);
        }
    }
}
