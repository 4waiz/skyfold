using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold
{
    public enum InteractorKind { Desktop, VRLeft, VRRight }

    /// <summary>
    /// Something in the street the player can use: car door, switches, levers, sockets.
    /// Desktop: look at it and press E. VR: point the controller ray (or reach) and pull the
    /// trigger, or squeeze the grip; XRI provides the hover highlight via an XRSimpleInteractable.
    /// </summary>
    public abstract class WorldInteractable : MonoBehaviour
    {
        public string verb = "Use";
        public float desktopRange = 2.8f;
        public bool interactable = true;
        public Transform promptAnchor;

        readonly List<Renderer> m_Renderers = new List<Renderer>();
        MaterialPropertyBlock m_Block;
        bool m_Highlighted;
        XRSimpleInteractable m_Xr;
        static readonly int HighlightId = Shader.PropertyToID("_Highlight");

        public virtual bool CanInteract(InteractorKind who) => interactable && isActiveAndEnabled;
        public virtual string Prompt => verb;
        /// <summary>Shown when the object is targeted but cannot be used yet.</summary>
        public virtual string BlockedReason => null;
        public abstract void Interact(InteractorKind who);

        public Vector3 PromptPosition => promptAnchor != null ? promptAnchor.position : transform.position + Vector3.up * 1.2f;

        protected virtual void Awake()
        {
            GetComponentsInChildren(true, m_Renderers);
            m_Xr = GetComponent<XRSimpleInteractable>();
            if (m_Xr != null) m_Xr.selectEntered.AddListener(OnXrSelect);
        }

        protected virtual void OnDestroy()
        {
            if (m_Xr != null) m_Xr.selectEntered.RemoveListener(OnXrSelect);
        }

        protected virtual void OnEnable() => DesktopInteractionScanner.Register(this);

        protected virtual void OnDisable()
        {
            DesktopInteractionScanner.Unregister(this);
            SetHighlighted(false);
        }

        void OnXrSelect(SelectEnterEventArgs args)
        {
            var rigs = PlayerRigs.Instance;
            var hand = rigs != null && rigs.vr != null && rigs.vr.LeftInteractor != null && (Object)args.interactorObject == rigs.vr.LeftInteractor ? InteractorKind.VRLeft : InteractorKind.VRRight;
            if (CanInteract(hand)) Interact(hand);
            // Simple interactables never stay selected.
            if (m_Xr.interactionManager != null) m_Xr.interactionManager.CancelInteractableSelection((IXRSelectInteractable)m_Xr);
        }

        public void SetHighlighted(bool on)
        {
            if (on == m_Highlighted) return;
            m_Highlighted = on;
            m_Block ??= new MaterialPropertyBlock();
            foreach (var r in m_Renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(m_Block);
                m_Block.SetFloat(HighlightId, on ? 1f : 0f);
                r.SetPropertyBlock(m_Block);
            }
        }
    }

    /// <summary>Desktop "look and press E" targeting from the first-person camera.</summary>
    public sealed class DesktopInteractionScanner : MonoBehaviour
    {
        public DesktopPlayer player;
        public float maxDistance = 3.2f;
        public LayerMask mask = ~0;

        public WorldInteractable Current { get; private set; }

        void Update()
        {
            var input = InputRouter.Instance;
            WorldInteractable found = null;
            if (input != null && input.Mode == PlayMode.Desktop && input.Context == InputContext.OnFoot && player != null && player.View == DesktopView.FirstPerson)
            {
                var ray = player.PointerRay();
                if (Physics.SphereCast(ray, 0.12f, out var hit, maxDistance, mask, QueryTriggerInteraction.Collide))
                {
                    var wi = hit.collider.GetComponentInParent<WorldInteractable>();
                    if (wi != null && hit.distance <= wi.desktopRange) found = wi;
                }
                if (found == null)
                {
                    // Generous fallback: nearest interactable roughly in view and close.
                    float best = 2.2f;
                    foreach (var wi in s_All)
                    {
                        if (wi == null || !wi.isActiveAndEnabled) continue;
                        Vector3 to = wi.transform.position - ray.origin;
                        float d = to.magnitude;
                        if (d > best || d > wi.desktopRange) continue;
                        if (Vector3.Angle(ray.direction, to) > 28f) continue;
                        best = d;
                        found = wi;
                    }
                }
            }

            if (found != Current)
            {
                if (Current != null) Current.SetHighlighted(false);
                Current = found;
                if (Current != null) Current.SetHighlighted(true);
            }

            if (Current != null && input != null && input.Interact.WasPressedThisFrame())
            {
                if (Current.CanInteract(InteractorKind.Desktop)) Current.Interact(InteractorKind.Desktop);
                else if (!string.IsNullOrEmpty(Current.BlockedReason)) HUDMessages.Toast(Current.BlockedReason);
            }
        }

        static readonly List<WorldInteractable> s_All = new List<WorldInteractable>();
        public static void Register(WorldInteractable wi) { if (!s_All.Contains(wi)) s_All.Add(wi); }
        public static void Unregister(WorldInteractable wi) => s_All.Remove(wi);
    }

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
