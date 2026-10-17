using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>On/off switch art for a menu toggle: the knob slides across and the track colours follow the row's focus.</summary>
    public sealed class SwitchVisual : MonoBehaviour
    {
        public Image track, knob, knobShadow;
        public TextMeshProUGUI state;
        public float travel = 15f;

        bool m_On, m_Active;
        float m_X;

        public void Init(bool on)
        {
            m_On = on;
            m_X = on ? travel : -travel;
            Refresh(true);
        }

        public void SetOn(bool on) { m_On = on; Refresh(false); }
        public void SetActive(bool active) { m_Active = active; Refresh(false); }

        void Refresh(bool snap)
        {
            if (track != null)
                track.color = m_On ? (m_Active ? UIStyle.TealGlow : UIStyle.Teal) : (m_Active ? new Color(1f, 1f, 1f, 0.32f) : UIStyle.Rail);
            if (state != null)
            {
                state.text = m_On ? "On" : "Off";
                state.color = m_Active ? UIStyle.Pearl : (m_On ? UIStyle.Teal : UIStyle.InkSoft);
            }
            if (snap) Place();
        }

        void Place()
        {
            if (knob != null) knob.rectTransform.anchoredPosition = new Vector2(m_X, 0f);
            if (knobShadow != null) knobShadow.rectTransform.anchoredPosition = new Vector2(m_X, -2f);
        }

        void Update()
        {
            float target = m_On ? travel : -travel;
            if (Mathf.Approximately(m_X, target)) return;
            // Quick ease so the knob visibly slides rather than jumping.
            m_X = Mathf.MoveTowards(m_X, target, Time.unscaledDeltaTime * travel * 2f / 0.12f);
            Place();
        }
    }
}
