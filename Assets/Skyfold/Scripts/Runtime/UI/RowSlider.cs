using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>
    /// A slider that fills a whole menu row. Only a press on the track (plus a little slack around the
    /// knob) drags the value; a press on the label just focuses the row, so clicking "Master" never
    /// snaps the volume to zero. The mouse wheel nudges the value in 5% steps while hovering the row.
    /// </summary>
    public sealed class RowSlider : Slider, IScrollHandler
    {
        public RectTransform hitArea;
        public float hitSlack = 20f;

        bool m_TrackPress;

        bool PressOnTrack(PointerEventData e)
        {
            if (hitArea == null) return true;
            var cam = e.pressEventCamera != null ? e.pressEventCamera : e.enterEventCamera;
            if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(hitArea, e.pointerPressRaycast.screenPosition, cam, out var local))
                return false;
            var r = hitArea.rect;
            return local.x >= r.xMin - hitSlack && local.x <= r.xMax + hitSlack;
        }

        public override void OnPointerDown(PointerEventData eventData)
        {
            m_TrackPress = eventData.button == PointerEventData.InputButton.Left && PressOnTrack(eventData);
            if (m_TrackPress)
            {
                base.OnPointerDown(eventData);
                return;
            }
            if (eventData.button == PointerEventData.InputButton.Left && IsInteractable() &&
                navigation.mode != Navigation.Mode.None && EventSystem.current != null)
                EventSystem.current.SetSelectedGameObject(gameObject, eventData);
        }

        public override void OnDrag(PointerEventData eventData)
        {
            if (m_TrackPress) base.OnDrag(eventData);
        }

        public override void OnPointerUp(PointerEventData eventData)
        {
            base.OnPointerUp(eventData);
            m_TrackPress = false;
        }

        public void OnScroll(PointerEventData eventData)
        {
            if (!IsActive() || !IsInteractable() || Mathf.Approximately(eventData.scrollDelta.y, 0f)) return;
            float step = wholeNumbers ? 1f : (maxValue - minValue) * 0.05f;
            value += Mathf.Sign(eventData.scrollDelta.y) * step;
        }
    }
}
