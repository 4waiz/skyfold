using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>VR: trigger while a hand ray or near-hover is on a WorldInteractable uses it.</summary>
    public sealed class VRUseHandler : MonoBehaviour
    {
        public VRRigController rig;

        public WorldInteractable LeftTarget { get; private set; }
        public WorldInteractable RightTarget { get; private set; }

        void Update()
        {
            var input = InputRouter.Instance;
            if (input == null || input.Mode != PlayMode.VR || rig == null) { Clear(); return; }
            var ctx = input.Context;
            if (ctx != InputContext.OnFoot && ctx != InputContext.Architect && ctx != InputContext.Cutscene) { Clear(); return; }

            Update(Hand.Left, ref m_Left, input.UseLeft.WasPressedThisFrame(), InteractorKind.VRLeft);
            Update(Hand.Right, ref m_Right, input.UseRight.WasPressedThisFrame(), InteractorKind.VRRight);
            LeftTarget = m_Left;
            RightTarget = m_Right;
        }

        WorldInteractable m_Left, m_Right;

        void Update(Hand hand, ref WorldInteractable current, bool pressed, InteractorKind kind)
        {
            WorldInteractable found = null;
            foreach (var h in rig.Hovered(hand))
            {
                if (h is Component c)
                {
                    var wi = c.GetComponentInParent<WorldInteractable>();
                    if (wi != null) { found = wi; break; }
                }
            }
            if (found != current)
            {
                if (current != null) current.SetHighlighted(false);
                current = found;
                if (current != null) { current.SetHighlighted(true); rig.Haptic(hand, 0.12f, 0.03f); }
            }
            if (pressed && current != null)
            {
                if (current.CanInteract(kind)) { current.Interact(kind); rig.Haptic(hand, 0.4f, 0.06f); }
                else if (!string.IsNullOrEmpty(current.BlockedReason)) HUDMessages.Toast(current.BlockedReason);
            }
        }

        void Clear()
        {
            if (m_Left != null) m_Left.SetHighlighted(false);
            if (m_Right != null) m_Right.SetHighlighted(false);
            m_Left = m_Right = null;
            LeftTarget = RightTarget = null;
        }
    }
}
