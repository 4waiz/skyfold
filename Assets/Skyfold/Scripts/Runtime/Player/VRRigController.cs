using System.Collections.Generic;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Inputs.Haptics;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Interactors;
using UnityEngine.XR.Interaction.Toolkit.Locomotion;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Comfort;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Turning;
using UnityEngine.XR.Interaction.Toolkit.Samples.StarterAssets;

namespace Skyfold
{
    public enum Hand { Left, Right }

    /// <summary>
    /// Wraps the XRI Starter Assets "XR Origin (XR Rig)": applies comfort settings, switches
    /// locomotion/grab per input context, seats the player in the car without rolling the
    /// camera, and provides haptics. Physical head tracking is never overridden per frame.
    /// </summary>
    public sealed class VRRigController : MonoBehaviour
    {
        public XROrigin origin;
        public float seatedRaise = 0.45f;

        Camera m_Camera;
        CharacterController m_Body;
        Transform m_Left, m_Right, m_CameraOffset, m_Locomotion;
        ControllerInputActionManager m_LeftManager, m_RightManager;
        NearFarInteractor m_LeftNearFar, m_RightNearFar;
        XRRayInteractor m_LeftTeleport, m_RightTeleport;
        HapticImpulsePlayer m_LeftHaptics, m_RightHaptics;
        SnapTurnProvider m_SnapTurn;
        ContinuousTurnProvider m_SmoothTurn;
        ContinuousMoveProvider m_Move;
        TunnelingVignetteController m_Vignette;
        InteractionLayerMask m_DefaultLayers;
        Transform m_HomeParent;
        Transform m_Seat, m_SeatEye;
        InputContext m_Context = InputContext.Menu;
        bool m_Ready;
        float m_LastYaw;
        bool m_HasLastYaw;

        public Camera Camera => m_Camera;
        public Transform Head => m_Camera != null ? m_Camera.transform : transform;
        public Transform LeftHand => m_Left;
        public Transform RightHand => m_Right;
        public NearFarInteractor LeftInteractor => m_LeftNearFar;
        public NearFarInteractor RightInteractor => m_RightNearFar;
        public TunnelingVignetteController Vignette => m_Vignette;
        public bool IsSeated => m_Seat != null;

        public Vector3 FeetPosition
        {
            get
            {
                if (m_Camera == null) return transform.position;
                var p = m_Camera.transform.position;
                return new Vector3(p.x, origin.Origin.transform.position.y, p.z);
            }
        }

        void Awake() => Setup();

        public void Setup()
        {
            if (m_Ready) return;
            if (origin == null) origin = GetComponentInChildren<XROrigin>(true);
            if (origin == null) { Debug.LogError("[SKYFOLD] VR rig has no XROrigin"); return; }
            m_Camera = origin.Camera;
            m_Body = origin.GetComponent<CharacterController>();
            m_CameraOffset = origin.CameraFloorOffsetObject != null ? origin.CameraFloorOffsetObject.transform : null;
            m_Left = FindDeep(origin.transform, "Left Controller");
            m_Right = FindDeep(origin.transform, "Right Controller");
            m_Locomotion = FindDeep(origin.transform, "Locomotion");
            m_HomeParent = origin.transform.parent;

            if (m_Left != null)
            {
                m_LeftManager = m_Left.GetComponent<ControllerInputActionManager>();
                m_LeftNearFar = m_Left.GetComponentInChildren<NearFarInteractor>(true);
                m_LeftHaptics = m_Left.GetComponent<HapticImpulsePlayer>();
                var t = FindDeep(m_Left, "Teleport Interactor");
                if (t != null) m_LeftTeleport = t.GetComponent<XRRayInteractor>();
            }
            if (m_Right != null)
            {
                m_RightManager = m_Right.GetComponent<ControllerInputActionManager>();
                m_RightNearFar = m_Right.GetComponentInChildren<NearFarInteractor>(true);
                m_RightHaptics = m_Right.GetComponent<HapticImpulsePlayer>();
                var t = FindDeep(m_Right, "Teleport Interactor");
                if (t != null) m_RightTeleport = t.GetComponent<XRRayInteractor>();
            }
            if (m_RightNearFar != null) m_DefaultLayers = m_RightNearFar.interactionLayers;

            m_SnapTurn = origin.GetComponentInChildren<SnapTurnProvider>(true);
            m_SmoothTurn = origin.GetComponentInChildren<ContinuousTurnProvider>(true);
            m_Move = origin.GetComponentInChildren<ContinuousMoveProvider>(true);
            m_Vignette = origin.GetComponentInChildren<TunnelingVignetteController>(true);

            // Features this game does not use. Jump would sit on A, which is the teleport button.
            SetChildActive(m_Locomotion, "Jump", false);
            SetChildActive(m_Locomotion, "Climb", false);
            SetChildActive(m_Locomotion, "Grab Move", false);
            var gaze = FindDeep(origin.transform, "Gaze Interactor");
            if (gaze != null) gaze.gameObject.SetActive(false);

            origin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Floor;
            m_Ready = true;
            ApplyComfort(SettingsStore.Current);
        }

        static void SetChildActive(Transform parent, string name, bool active)
        {
            if (parent == null) return;
            var c = FindDeep(parent, name);
            if (c != null) c.gameObject.SetActive(active);
        }

        public static Transform FindDeep(Transform root, string name)
        {
            if (root == null) return null;
            if (root.name == name) return root;
            for (int i = 0; i < root.childCount; i++)
            {
                var r = FindDeep(root.GetChild(i), name);
                if (r != null) return r;
            }
            return null;
        }

        // ------------------------------------------------------------------ comfort
        public void ApplyComfort(GameSettings s)
        {
            if (!m_Ready) return;
            if (m_LeftManager != null)
            {
                m_LeftManager.smoothMotionEnabled = s.moveMode == MoveMode.Smooth;
                m_LeftManager.smoothTurnEnabled = false;
            }
            if (m_RightManager != null)
            {
                m_RightManager.smoothMotionEnabled = false;  // right stick turns, A teleports
                m_RightManager.smoothTurnEnabled = s.turnMode == TurnMode.Smooth;
            }
            if (m_SnapTurn != null) { m_SnapTurn.turnAmount = s.snapAngle; m_SnapTurn.enableTurnAround = false; }
            if (m_SmoothTurn != null) { m_SmoothTurn.turnSpeed = s.smoothTurnSpeed; m_SmoothTurn.enableTurnAround = false; }
            if (m_Move != null) m_Move.moveSpeed = s.moveSpeed;

            if (m_Vignette != null)
            {
                var p = m_Vignette.defaultParameters;
                p.apertureSize = Mathf.Lerp(0.95f, 0.55f, s.vignetteStrength);
                p.featheringEffect = 0.25f;
                p.easeInTime = 0.25f;
                p.easeOutTime = 0.35f;
                foreach (var provider in m_Vignette.locomotionVignetteProviders)
                {
                    bool continuous = provider.locomotionProvider is ContinuousMoveProvider || provider.locomotionProvider is ContinuousTurnProvider;
                    provider.enabled = s.vignette && continuous;
                }
            }
        }

        void LateUpdate()
        {
            if (!m_Ready || m_CameraOffset == null) return;
            var s = SettingsStore.Current;
            float y = s.heightOffset + (s.seated ? seatedRaise : 0f);
            var lp = m_CameraOffset.localPosition;
            if (Mathf.Abs(lp.y - y) > 0.0005f) m_CameraOffset.localPosition = new Vector3(lp.x, y, lp.z);
        }

        // ------------------------------------------------------------------ contexts
        public void SetContext(InputContext ctx)
        {
            if (!m_Ready) return;
            m_Context = ctx;
            bool walk = ctx == InputContext.OnFoot || ctx == InputContext.Architect || ctx == InputContext.Cutscene;
            bool grab = walk;
            if (m_LeftManager != null) m_LeftManager.enabled = walk;
            if (m_RightManager != null) m_RightManager.enabled = walk;
            if (m_Locomotion != null && m_Locomotion.gameObject.activeSelf != (walk && !IsSeated))
                m_Locomotion.gameObject.SetActive(walk && !IsSeated);
            if (!walk)
            {
                if (m_LeftTeleport != null) m_LeftTeleport.gameObject.SetActive(false);
                if (m_RightTeleport != null) m_RightTeleport.gameObject.SetActive(false);
            }
            // XRI hides a hand's near-far pointer while A aims a teleport and restores it only from the release
            // callback, which a disabled controller manager never gets: make sure both pointers exist again.
            if (m_LeftNearFar != null && !m_LeftNearFar.gameObject.activeSelf) m_LeftNearFar.gameObject.SetActive(true);
            if (m_RightNearFar != null && !m_RightNearFar.gameObject.activeSelf) m_RightNearFar.gameObject.SetActive(true);
            // Near-far interactors stay on for UI rays; grabbing is limited by interaction layers.
            if (m_LeftNearFar != null) m_LeftNearFar.interactionLayers = grab ? m_DefaultLayers : 0;
            if (m_RightNearFar != null) m_RightNearFar.interactionLayers = grab ? m_DefaultLayers : 0;
            if (m_Body != null) m_Body.enabled = !IsSeated;
        }

        // ------------------------------------------------------------------ movement helpers
        /// <summary>Moves the rig so the user's feet land on the anchor and their view faces its yaw.</summary>
        public void TeleportTo(Vector3 feet, float yaw)
        {
            if (!m_Ready) return;
            m_LastYaw = yaw;
            m_HasLastYaw = true;
            bool bodyWasEnabled = m_Body != null && m_Body.enabled;
            if (m_Body != null) m_Body.enabled = false;
            var forward = Quaternion.Euler(0f, yaw, 0f) * Vector3.forward;
            origin.MatchOriginUpCameraForward(Vector3.up, forward);
            Vector3 cam = m_Camera.transform.position;
            Vector3 originPos = origin.Origin.transform.position;
            Vector3 camFloor = new Vector3(cam.x, originPos.y, cam.z);
            origin.Origin.transform.position += feet - camFloor;
            if (m_Body != null) m_Body.enabled = bodyWasEnabled;
            Physics.SyncTransforms();
        }

        /// <summary>Seats the player: parents the rig to a yaw-only seat and lines the eyes up with it once.</summary>
        public void AttachToSeat(Transform seat, Transform eye)
        {
            if (!m_Ready || seat == null) return;
            m_Seat = seat;
            m_SeatEye = eye != null ? eye : seat;
            if (m_Body != null) m_Body.enabled = false;
            if (m_Locomotion != null) m_Locomotion.gameObject.SetActive(false);
            origin.transform.SetParent(seat, true);
            Recenter();
        }

        public void Recenter()
        {
            if (!m_Ready) return;
            if (m_Seat != null)
            {
                Vector3 fwd = Vector3.ProjectOnPlane(m_Seat.forward, Vector3.up).normalized;
                origin.MatchOriginUpCameraForward(Vector3.up, fwd);
                origin.Origin.transform.position += m_SeatEye.position - m_Camera.transform.position;
            }
            else if (m_HasLastYaw)
            {
                // Standing: turn back to the facing of the last placement (the plinth, a kiosk, a start spot)
                // where you stand now. Matching the camera's own forward, as before, was a no-op.
                TeleportTo(FeetPosition, m_LastYaw);
            }
        }

        public void DetachFromSeat(Vector3 feet, float yaw)
        {
            if (!m_Ready) return;
            m_Seat = null;
            m_SeatEye = null;
            origin.transform.SetParent(m_HomeParent, true);
            origin.transform.rotation = Quaternion.Euler(0f, origin.transform.eulerAngles.y, 0f);
            TeleportTo(feet, yaw);
            if (m_Body != null) m_Body.enabled = true;
            SetContext(m_Context);
        }

        public bool Haptic(Hand hand, float amplitude, float duration)
        {
            var p = hand == Hand.Left ? m_LeftHaptics : m_RightHaptics;
            return p != null && p.SendHapticImpulse(Mathf.Clamp01(amplitude), duration);
        }

        public void HapticBoth(float amplitude, float duration)
        {
            Haptic(Hand.Left, amplitude, duration);
            Haptic(Hand.Right, amplitude, duration);
        }

        /// <summary>The hand whose interactor is selecting the given interactable (for haptics).</summary>
        public Hand? HandSelecting(IXRSelectInteractable interactable)
        {
            if (m_LeftNearFar != null && m_LeftNearFar.IsSelecting(interactable)) return Hand.Left;
            if (m_RightNearFar != null && m_RightNearFar.IsSelecting(interactable)) return Hand.Right;
            return null;
        }

        public IEnumerable<IXRHoverInteractable> Hovered(Hand hand)
        {
            var nf = hand == Hand.Left ? m_LeftNearFar : m_RightNearFar;
            if (nf == null) yield break;
            foreach (var h in nf.interactablesHovered) yield return h;
        }
    }
}
