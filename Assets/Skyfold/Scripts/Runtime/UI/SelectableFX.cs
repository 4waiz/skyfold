using System;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>Hover/focus/disabled visuals and sounds for every menu control (mouse, keyboard and XR rays).</summary>
    public sealed class SelectableFX : MonoBehaviour, ISelectHandler, IDeselectHandler, IPointerEnterHandler, IPointerExitHandler
    {
        Image m_Bg;
        TextMeshProUGUI m_Label, m_Detail;
        Color? m_DetailNormal;
        bool m_Primary, m_Focused, m_Hovered;
        Selectable m_Selectable;
        float m_Scale = 1f;
        Action<bool> m_OnActive;
        bool m_HasApplied, m_LastActive;

        /// <param name="detailNormal">Colour of the detail text when the row is not focused (default: soft ink).</param>
        /// <param name="onActive">Called with true/false whenever the row gains or loses focus/hover, so a widget can
        /// recolour its own parts (rails, knobs, arrows) for contrast on the teal focus colour.</param>
        public void Init(Image bg, TextMeshProUGUI label, TextMeshProUGUI detail, bool primary, Color? detailNormal = null, Action<bool> onActive = null)
        {
            m_Bg = bg;
            m_Label = label;
            m_Detail = detail;
            m_DetailNormal = detailNormal;
            m_Primary = primary;
            m_OnActive = onActive;
            m_Selectable = GetComponent<Selectable>();
            Apply();
        }

        public void OnSelect(BaseEventData e) { m_Focused = true; Apply(); AudioDirector.Instance?.PlayUI("ui_hover", 0.5f); }
        public void OnDeselect(BaseEventData e) { m_Focused = false; Apply(); }
        public void OnPointerEnter(PointerEventData e)
        {
            m_Hovered = true;
            Apply();
            if (m_Selectable == null || !m_Selectable.IsInteractable()) return;
            AudioDirector.Instance?.PlayUI("ui_hover", 0.4f);
            // Hover moves keyboard focus here, so the mouse/ray and the keyboard never highlight two rows at once.
            var es = EventSystem.current;
            if (es != null && es.currentSelectedGameObject != gameObject && !es.alreadySelecting) es.SetSelectedGameObject(gameObject);
        }
        public void OnPointerExit(PointerEventData e) { m_Hovered = false; Apply(); }

        void OnDisable()
        {
            // A rebuilt or hidden menu must not come back stuck in the hover state.
            m_Hovered = false;
            m_Focused = false;
            m_Scale = 1f;
            transform.localScale = Vector3.one;
            Apply();
        }

        void Update()
        {
            float target = (m_Focused || m_Hovered) && Interactable ? 1.025f : 1f;
            m_Scale = Mathf.MoveTowards(m_Scale, target, Time.unscaledDeltaTime * 0.6f);
            transform.localScale = new Vector3(m_Scale, m_Scale, 1f);
            if (m_Selectable != null && m_LastInteractable != m_Selectable.IsInteractable()) Apply();
        }

        bool m_LastInteractable = true;
        bool Interactable => m_Selectable == null || m_Selectable.IsInteractable();

        void Apply()
        {
            if (m_Bg == null) return;
            m_LastInteractable = Interactable;
            bool active = (m_Focused || m_Hovered) && Interactable;
            Color bg = m_Primary ? UIStyle.Teal : UIStyle.PearlDeep;
            Color fg = m_Primary ? UIStyle.Pearl : UIStyle.Ink;
            if (active)
            {
                bg = m_Primary ? UIStyle.TealLight : UIStyle.Teal;
                fg = UIStyle.Pearl;
            }
            if (!Interactable)
            {
                bg = new Color(bg.r, bg.g, bg.b, 0.45f);
                fg = new Color(fg.r, fg.g, fg.b, 0.45f);
            }
            m_Bg.color = bg;
            if (m_Label != null) m_Label.color = fg;
            if (m_Detail != null)
            {
                Color d = active || m_Primary ? UIStyle.Pearl : (m_DetailNormal ?? UIStyle.InkSoft);
                if (!Interactable) d.a = 0.45f;
                m_Detail.color = d;
            }
            if (!m_HasApplied || active != m_LastActive)
            {
                m_HasApplied = true;
                m_LastActive = active;
                m_OnActive?.Invoke(active);
            }
        }
    }
}
