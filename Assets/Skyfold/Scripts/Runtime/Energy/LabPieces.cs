using System;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold
{
    /// <summary>
    /// A block on the lab table you pick up and drop somewhere (VR: grip, desktop: hold the left mouse button).
    /// Like the road pieces, it never falls: on release the owning game snaps it into a slot or glides it home.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public sealed class LabToken : MonoBehaviour
    {
        public string tokenId;
        public int kind;
        public string displayName;
        public Vector3 homePosition;
        public Quaternion homeRotation = Quaternion.identity;

        /// <summary>Asked when a hand tries to pick the token up; false refuses (e.g. the puzzle is already solved).</summary>
        public Func<LabToken, bool> CanPick;
        public Action<LabToken> Picked;
        public Action<LabToken> Dropped;

        public XRGrabInteractable Grab { get; private set; }
        public bool Held { get; private set; }
        public bool Moving => m_MoveT < 1f;
        public bool DesktopHeld { get; private set; }

        Vector3 m_FromPos, m_ToPos;
        Quaternion m_FromRot, m_ToRot;
        float m_MoveT = 1f, m_MoveDuration = 0.3f;

        /// <summary>Call once the token's colliders exist: adds the XR grab with the same settings as the road pieces.</summary>
        public void Setup()
        {
            var rb = GetComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            Grab = gameObject.AddComponent<XRGrabInteractable>();
            Grab.movementType = XRBaseInteractable.MovementType.Kinematic;
            Grab.throwOnDetach = false;
            Grab.useDynamicAttach = true;
            Grab.trackRotation = true;
            Grab.retainTransformParent = true;
            Grab.farAttachMode = UnityEngine.XR.Interaction.Toolkit.Attachment.InteractableFarAttachMode.Far;
            Grab.selectEntered.AddListener(OnGrabbed);
            Grab.selectExited.AddListener(OnReleased);
        }

        void OnDestroy()
        {
            if (Grab == null) return;
            Grab.selectEntered.RemoveListener(OnGrabbed);
            Grab.selectExited.RemoveListener(OnReleased);
        }

        void OnGrabbed(SelectEnterEventArgs args)
        {
            if (!TryBegin())
            {
                if (Grab.interactionManager != null) Grab.interactionManager.CancelInteractableSelection((IXRSelectInteractable)Grab);
                return;
            }
            var rigs = PlayerRigs.Instance;
            if (rigs != null && rigs.Mode == PlayMode.VR && rigs.vr != null)
            {
                var hand = rigs.vr.HandSelecting(Grab);
                if (hand.HasValue) rigs.vr.Haptic(hand.Value, 0.25f, 0.05f);
            }
        }

        void OnReleased(SelectExitEventArgs args)
        {
            if (!Held) return;
            Held = false;
            Dropped?.Invoke(this);
        }

        bool TryBegin()
        {
            if (Moving || (CanPick != null && !CanPick(this))) return false;
            Held = true;
            m_MoveT = 1f;
            AudioDirector.Instance?.PlayAt("piece_pickup", transform.position, 0.8f);
            Picked?.Invoke(this);
            return true;
        }

        // ------------------------------------------------------------------ desktop
        public bool BeginDesktopHold()
        {
            if (!TryBegin()) return false;
            DesktopHeld = true;
            return true;
        }

        public void DesktopFollow(Vector3 target)
        {
            float k = 1f - Mathf.Exp(-18f * UnityEngine.Time.unscaledDeltaTime);
            transform.position = Vector3.Lerp(transform.position, target, k);
            transform.rotation = Quaternion.Slerp(transform.rotation, homeRotation, k);
        }

        public void EndDesktopHold()
        {
            if (!DesktopHeld) return;
            DesktopHeld = false;
            if (!Held) return;
            Held = false;
            Dropped?.Invoke(this);
        }

        /// <summary>Lets go of the token wherever it is held (board change, pause, restart) without dropping it into a slot.</summary>
        public void ForceRelease()
        {
            DesktopHeld = false;
            bool wasHeld = Held;
            Held = false;
            if (Grab != null && Grab.isSelected && Grab.interactionManager != null)
                Grab.interactionManager.CancelInteractableSelection((IXRSelectInteractable)Grab);
            if (wasHeld) MoveTo(homePosition, homeRotation, 0.3f);
        }

        // ------------------------------------------------------------------ motion
        public void MoveTo(Vector3 pos, Quaternion rot, float duration = 0.28f)
        {
            m_FromPos = transform.position;
            m_FromRot = transform.rotation;
            m_ToPos = pos;
            m_ToRot = rot;
            m_MoveT = 0f;
            m_MoveDuration = Mathf.Max(0.05f, duration);
        }

        public void SetImmediate(Vector3 pos, Quaternion rot)
        {
            transform.SetPositionAndRotation(pos, rot);
            m_MoveT = 1f;
        }

        public void GoHome(float duration = 0.4f) => MoveTo(homePosition, homeRotation, duration);

        void Update()
        {
            if (m_MoveT >= 1f) return;
            m_MoveT = Mathf.Min(1f, m_MoveT + UnityEngine.Time.unscaledDeltaTime / m_MoveDuration);
            float e = 1f - Mathf.Pow(1f - m_MoveT, 3f);
            Vector3 p = Vector3.Lerp(m_FromPos, m_ToPos, e) + Vector3.up * Mathf.Sin(e * Mathf.PI) * 0.04f;
            transform.SetPositionAndRotation(p, Quaternion.Slerp(m_FromRot, m_ToRot, e));
        }

        public void SetGrabbable(bool on)
        {
            if (Grab != null) Grab.enabled = on;
        }
    }

    /// <summary>
    /// Something on the lab table you point at and use: a pipe to turn, a mudflat to plant. VR: trigger with the
    /// ray (or grip); desktop: click. Built on <see cref="WorldInteractable"/>, so it gets the same highlight and
    /// hand haptics as the switches in the street.
    /// </summary>
    public sealed class LabButton : WorldInteractable
    {
        public Func<bool> Usable;
        public Func<string> Blocked;
        public Action<InteractorKind> Pressed;

        public override bool CanInteract(InteractorKind who) => base.CanInteract(who) && (Usable == null || Usable());
        public override string BlockedReason => Blocked != null ? Blocked() : null;
        public override void Interact(InteractorKind who) => Pressed?.Invoke(who);

        /// <summary>Adds an XR simple interactable and a LabButton to a node whose collider and renderers already exist.</summary>
        public static LabButton Make(GameObject go, string verb)
        {
            LabKit.SetLayer(go, "Interactable");
            go.AddComponent<XRSimpleInteractable>();
            var b = go.AddComponent<LabButton>();
            b.verb = verb;
            b.desktopRange = 8f;
            return b;
        }
    }
}
