using UnityEngine;

namespace Skyfold
{
    /// <summary>Owns the desktop and VR rigs and guarantees exactly one is active.</summary>
    public sealed class PlayerRigs : MonoBehaviour
    {
        public static PlayerRigs Instance { get; private set; }

        public DesktopPlayer desktop;
        public VRRigController vr;

        public PlayMode Mode { get; private set; } = PlayMode.Desktop;
        public bool IsDriving { get; set; }

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public Camera ActiveCamera => Mode == PlayMode.VR && vr != null ? vr.Camera : desktop != null ? desktop.cam : Camera.main;
        public Transform Head => Mode == PlayMode.VR && vr != null ? vr.Head : (desktop.cam != null ? desktop.cam.transform : desktop.Head);
        public Vector3 FeetPosition
        {
            get
            {
                if (IsDriving && CourierVehicle.Instance != null) return CourierVehicle.Instance.Position;
                return Mode == PlayMode.VR && vr != null ? vr.FeetPosition : desktop.FeetPosition;
            }
        }

        public Vector3 Forward
        {
            get
            {
                var f = Vector3.ProjectOnPlane(Head.forward, Vector3.up);
                return f.sqrMagnitude > 0.001f ? f.normalized : Vector3.forward;
            }
        }

        public void SetMode(PlayMode mode)
        {
            Mode = mode;
            if (desktop != null) desktop.gameObject.SetActive(mode == PlayMode.Desktop);
            // The desktop camera is unparented from its rig for the title, Atelier and driving views, so switching
            // the rig off does not switch it off. Left on in VR it would draw over the headset image (it renders
            // after the XR camera) and keep a second AudioListener.
            if (desktop != null && desktop.cam != null) desktop.cam.gameObject.SetActive(mode == PlayMode.Desktop);
            if (vr != null) vr.gameObject.SetActive(mode == PlayMode.VR);
            if (mode == PlayMode.VR && vr != null) vr.Setup();
            Debug.Log("[SKYFOLD] Active rig: " + mode);
        }

        public void TeleportTo(Anchor a) => TeleportTo(a.Position, a.Yaw);

        public void TeleportTo(Vector3 feet, float yaw)
        {
            if (Mode == PlayMode.VR && vr != null) vr.TeleportTo(feet, yaw);
            else if (desktop != null) desktop.TeleportTo(feet, yaw);
        }

        public void Haptic(Hand hand, float amplitude, float duration)
        {
            if (Mode == PlayMode.VR && vr != null) vr.Haptic(hand, amplitude, duration);
        }

        public void HapticBoth(float amplitude, float duration)
        {
            if (Mode == PlayMode.VR && vr != null) vr.HapticBoth(amplitude, duration);
        }
    }
}
