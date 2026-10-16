using UnityEngine;

namespace Skyfold
{
    /// <summary>Desktop plinth controls: click-hold to pick a piece, drag it over the table, R turns it, release to place.</summary>
    public sealed class TabletopDesktopInput : MonoBehaviour
    {
        public DesktopPlayer player;
        public TabletopController controller;
        public LayerMask pieceMask;
        public Vector2 tableHalfExtents = new Vector2(0.78f, 0.58f);
        public float holdLift = 0.05f;

        ModulePiece m_Held;
        ModulePiece m_Hover;

        public ModulePiece Held => m_Held;

        void Update()
        {
            var input = InputRouter.Instance;
            bool active = input != null && input.Mode == PlayMode.Desktop && input.Context == InputContext.Architect && player != null && player.View == DesktopView.Architect;
            if (!active)
            {
                if (m_Held != null) { var h = m_Held; m_Held = null; h.EndDesktopHold(); controller.Release(h); }
                SetHover(null);
                return;
            }

            var ray = player.PointerRay();
            if (m_Held == null)
            {
                ModulePiece under = null;
                if (Physics.Raycast(ray, out var hit, 6f, pieceMask, QueryTriggerInteraction.Collide))
                    under = hit.collider.GetComponentInParent<ModulePiece>();
                SetHover(under);
                if (input.Drag.WasPressedThisFrame() && under != null && under.State != PieceState.Moving)
                {
                    if (controller.BeginHold(under))
                    {
                        m_Held = under;
                        under.BeginDesktopHold();
                        SetHover(null);
                    }
                }
                return;
            }

            var mini = controller.mini;
            float y = mini.TableHeight + holdLift;
            var plane = new Plane(Vector3.up, new Vector3(0f, y, 0f));
            if (plane.Raycast(ray, out float enter))
            {
                Vector3 p = ray.GetPoint(enter);
                Vector3 local = mini.transform.parent != null ? mini.transform.parent.InverseTransformPoint(p) : p;
                Vector3 centre = mini.transform.parent != null ? mini.transform.parent.InverseTransformPoint(mini.CityToWorld(CityLayout.CityCenter)) : mini.CityToWorld(CityLayout.CityCenter);
                local.x = Mathf.Clamp(local.x, centre.x - tableHalfExtents.x, centre.x + tableHalfExtents.x);
                local.z = Mathf.Clamp(local.z, centre.z - tableHalfExtents.y - 0.12f, centre.z + tableHalfExtents.y);
                p = mini.transform.parent != null ? mini.transform.parent.TransformPoint(local) : local;
                p.y = y;
                m_Held.DesktopFollow(p);
            }
            if (input.Rotate.WasPressedThisFrame()) m_Held.DesktopRotate();
            if (input.Drag.WasReleasedThisFrame())
            {
                var h = m_Held;
                m_Held = null;
                h.EndDesktopHold();
                controller.Release(h);
            }
        }

        void SetHover(ModulePiece p)
        {
            if (p == m_Hover) return;
            m_Hover = p;
            HUDMessages.SetCursorHint(p != null ? ModuleInfo.DisplayName(p.type) + " - hold left mouse to pick up" : null);
        }
    }
}
