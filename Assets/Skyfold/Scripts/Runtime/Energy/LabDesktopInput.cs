using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Laptop controls for the lab, in the plinth (Architect) view: hold the left mouse button on an energy block to
    /// drag it, release to drop it; click a pipe or a mudflat to use it. Uses the same Drag/Point actions as the
    /// road pieces, so the bindings and the cursor behave exactly as they did at the plinth.
    /// </summary>
    public sealed class LabDesktopInput : MonoBehaviour
    {
        public float holdLift = 0.07f;
        public Vector2 tableHalfExtents = new Vector2(0.7f, 0.48f);

        LabToken m_Held;
        LabButton m_Hover;
        LabToken m_HoverToken;
        bool m_HintSet;
        int m_Mask;

        void Awake() => m_Mask = LayerMask.GetMask("Interactable");

        void Update()
        {
            var lab = EnergyLab.Instance;
            var input = InputRouter.Instance;
            var rigs = PlayerRigs.Instance;
            bool active = lab != null && lab.Active != null && input != null && rigs != null && rigs.desktop != null &&
                          input.Mode == PlayMode.Desktop && input.Context == InputContext.Architect && rigs.desktop.View == DesktopView.Architect;
            if (!active)
            {
                if (m_Held != null) { var h = m_Held; m_Held = null; h.EndDesktopHold(); }
                SetHover(null, null);
                return;
            }

            var ray = rigs.desktop.PointerRay();
            if (m_Held == null)
            {
                LabButton button = null;
                LabToken token = null;
                if (Physics.Raycast(ray, out var hit, 8f, m_Mask, QueryTriggerInteraction.Collide))
                {
                    token = hit.collider.GetComponentInParent<LabToken>();
                    if (token == null) button = hit.collider.GetComponentInParent<LabButton>();
                }
                SetHover(button, token);
                if (!input.Drag.WasPressedThisFrame()) return;
                if (token != null && token.BeginDesktopHold())
                {
                    m_Held = token;
                    SetHover(null, null);
                }
                else if (button != null)
                {
                    if (button.CanInteract(InteractorKind.Desktop)) button.Interact(InteractorKind.Desktop);
                    else if (!string.IsNullOrEmpty(button.BlockedReason)) HUDMessages.Toast(button.BlockedReason);
                }
                return;
            }

            // Dragging: follow the cursor on a plane just above the table, kept over the table.
            if (!m_Held.Held) { m_Held.EndDesktopHold(); m_Held = null; return; }
            var labT = lab.transform;
            float y = labT.position.y + holdLift;
            var plane = new Plane(Vector3.up, new Vector3(0f, y, 0f));
            if (plane.Raycast(ray, out float enter))
            {
                Vector3 local = labT.InverseTransformPoint(ray.GetPoint(enter));
                local.x = Mathf.Clamp(local.x, -tableHalfExtents.x, tableHalfExtents.x);
                local.z = Mathf.Clamp(local.z, -tableHalfExtents.y, tableHalfExtents.y);
                local.y = holdLift;
                m_Held.DesktopFollow(labT.TransformPoint(local));
            }
            if (input.Drag.WasReleasedThisFrame())
            {
                var h = m_Held;
                m_Held = null;
                h.EndDesktopHold();
            }
        }

        void SetHover(LabButton b, LabToken t)
        {
            if (b != m_Hover)
            {
                if (m_Hover != null) m_Hover.SetHighlighted(false);
                m_Hover = b;
                if (m_Hover != null) m_Hover.SetHighlighted(true);
            }
            m_HoverToken = t;
            string hint = t != null ? t.displayName + " block - hold the left mouse button to drag it"
                : b != null ? (b.CanInteract(InteractorKind.Desktop) ? "Click: " + b.Prompt : b.BlockedReason) : null;
            // Only clear a hint this script set, so the road pieces' own hover hint is left alone.
            if (hint == null && !m_HintSet) return;
            m_HintSet = hint != null;
            HUDMessages.SetCursorHint(hint);
        }
    }
}
