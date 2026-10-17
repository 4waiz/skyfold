using System;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>An option row that cycles with left/right, submit or a click (keyboard, mouse and XR friendly).</summary>
    public sealed class ChoiceSelectable : Selectable, ISubmitHandler, IPointerClickHandler
    {
        string[] m_Options;
        int m_Index;
        TextMeshProUGUI m_Value;
        Action<int> m_OnChange;
        RectTransform m_Prev, m_Next;

        public int Index => m_Index;

        public void Init(string[] options, int index, TextMeshProUGUI value, Action<int> onChange, RectTransform prev = null, RectTransform next = null)
        {
            m_Options = options;
            m_Index = Math.Max(0, Math.Min(options.Length - 1, index));
            m_Value = value;
            m_OnChange = onChange;
            m_Prev = prev;
            m_Next = next;
        }

        void Step(int delta)
        {
            if (!IsInteractable() || m_Options == null || m_Options.Length == 0) return;
            m_Index = (m_Index + delta + m_Options.Length) % m_Options.Length;
            if (m_Value != null) m_Value.text = m_Options[m_Index];
            AudioDirector.Instance?.PlayUI("ui_toggle");
            m_OnChange?.Invoke(m_Index);
        }

        public override void OnMove(AxisEventData eventData)
        {
            if (eventData.moveDir == MoveDirection.Left) { Step(-1); eventData.Use(); return; }
            if (eventData.moveDir == MoveDirection.Right) { Step(1); eventData.Use(); return; }
            base.OnMove(eventData);
        }

        public void OnSubmit(BaseEventData eventData) => Step(1);

        /// <summary>True when the press lands on an arrow, with generous horizontal slack and the full row height.</summary>
        static bool Over(RectTransform arrow, PointerEventData e, float slack)
        {
            if (arrow == null) return false;
            var cam = e.pressEventCamera != null ? e.pressEventCamera : e.enterEventCamera;
            if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(arrow, e.position, cam, out var local)) return false;
            return Mathf.Abs(local.x - arrow.rect.center.x) <= arrow.rect.width * 0.5f + slack;
        }

        public void OnPointerClick(PointerEventData eventData)
        {
            if (eventData.button != PointerEventData.InputButton.Left) return;
            // The left arrow steps back; the right arrow, the value and the label step forward.
            Step(Over(m_Prev, eventData, 22f) ? -1 : 1);
        }
    }
}
