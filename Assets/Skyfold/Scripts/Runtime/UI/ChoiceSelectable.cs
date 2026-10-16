using System;
using TMPro;
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

        public int Index => m_Index;

        public void Init(string[] options, int index, TextMeshProUGUI value, Action<int> onChange)
        {
            m_Options = options;
            m_Index = Math.Max(0, Math.Min(options.Length - 1, index));
            m_Value = value;
            m_OnChange = onChange;
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

        public void OnPointerClick(PointerEventData eventData)
        {
            if (eventData.button != PointerEventData.InputButton.Left) return;
            // Clicking the left arrow area steps back; anywhere else steps forward.
            var rt = (UnityEngine.RectTransform)transform;
            bool back = false;
            if (UnityEngine.RectTransformUtility.ScreenPointToLocalPointInRectangle(rt, eventData.position, eventData.pressEventCamera, out var local))
            {
                float fromRight = rt.rect.xMax - local.x;
                back = fromRight > 330f && fromRight < 400f;
            }
            Step(back ? -1 : 1);
        }
    }
}
