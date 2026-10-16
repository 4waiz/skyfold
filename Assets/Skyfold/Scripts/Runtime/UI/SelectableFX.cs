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
        bool m_Primary, m_Focused, m_Hovered;
        Selectable m_Selectable;
        float m_Scale = 1f;

        public void Init(Image bg, TextMeshProUGUI label, TextMeshProUGUI detail, bool primary)
        {
            m_Bg = bg;
            m_Label = label;
            m_Detail = detail;
            m_Primary = primary;
            m_Selectable = GetComponent<Selectable>();
            Apply();
        }

        public void OnSelect(BaseEventData e) { m_Focused = true; Apply(); AudioDirector.Instance?.PlayUI("ui_hover", 0.5f); }
        public void OnDeselect(BaseEventData e) { m_Focused = false; Apply(); }
        public void OnPointerEnter(PointerEventData e) { m_Hovered = true; Apply(); if (m_Selectable != null && m_Selectable.IsInteractable()) AudioDirector.Instance?.PlayUI("ui_hover", 0.4f); }
        public void OnPointerExit(PointerEventData e) { m_Hovered = false; Apply(); }

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
            if (m_Detail != null) m_Detail.color = active ? UIStyle.Pearl : (m_Primary ? UIStyle.Pearl : UIStyle.InkSoft);
        }
    }
}
