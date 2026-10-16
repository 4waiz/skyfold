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
}
