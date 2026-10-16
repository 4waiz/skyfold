using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.Management;
using Debug = UnityEngine.Debug;

namespace Skyfold
{
    public enum XRState { Off, Starting, Running, Failed, Stopping }

    /// <summary>
    /// Desktop-first XR lifecycle. XR is never initialised at startup; Enter VR initialises the
    /// OpenXR loader, checks the display subsystem is really running, then starts subsystems.
    /// Failures are logged with a plain-language reason and leave the desktop game usable.
    /// </summary>
    public sealed class XRBootstrap : MonoBehaviour
    {
        public static XRBootstrap Instance { get; private set; }

        public XRState State { get; private set; } = XRState.Off;
        public string LastError { get; private set; } = "";
        public string RuntimeName { get; private set; } = "";
        public int Attempts { get; private set; }
        public event Action<XRState> StateChanged;

        /// <summary>True when the headset reports a user wearing it (when the runtime exposes it).</summary>
        public bool UserPresent { get; private set; } = true;
        public bool ControllersTracked { get; private set; } = true;
        public bool LeftTracked { get; private set; }
        public bool RightTracked { get; private set; }

        readonly List<InputDevice> m_Devices = new List<InputDevice>();

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        void SetState(XRState s)
        {
            State = s;
            StateChanged?.Invoke(s);
        }

        public static bool MetaLinkServiceRunning()
        {
            try
            {
                return Process.GetProcessesByName("OVRServer_x64").Length > 0;
            }
            catch { return false; }
        }

        public IEnumerator StartXR(float displayTimeout = 6f)
        {
            if (State == XRState.Running || State == XRState.Starting) yield break;
            Attempts++;
            LastError = "";
            SetState(XRState.Starting);
            var general = XRGeneralSettings.Instance;
            var manager = general != null ? general.Manager : null;
            if (manager == null)
            {
                Fail("XR settings are missing from this build.");
                yield break;
            }

            if (manager.activeLoader != null)
            {
                // Clean up a half-started previous attempt before retrying.
                manager.StopSubsystems();
                manager.DeinitializeLoader();
                yield return null;
            }

            Debug.Log("[SKYFOLD] XR: initialising OpenXR loader (attempt " + Attempts + ")");
            yield return manager.InitializeLoader();
            if (manager.activeLoader == null)
            {
                Fail(MetaLinkServiceRunning()
                    ? "The headset did not answer. Put on the Quest 3, connect Link (cable or Air Link) and wait for the Link home screen, then press Retry."
                    : "Meta Horizon Link is not running on this PC. Start the Meta Horizon Link app, connect the Quest 3, then press Retry.");
                yield break;
            }

            manager.StartSubsystems();
            var display = manager.activeLoader.GetLoadedSubsystem<XRDisplaySubsystem>();
            float t = 0f;
            while ((display == null || !display.running) && t < displayTimeout)
            {
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            if (display == null || !display.running)
            {
                manager.StopSubsystems();
                manager.DeinitializeLoader();
                Fail("OpenXR started but no headset display came up. Check that Link is active in the headset, then press Retry.");
                yield break;
            }

            try
            {
                RuntimeName = UnityEngine.XR.OpenXR.OpenXRRuntime.name + " " + UnityEngine.XR.OpenXR.OpenXRRuntime.version;
            }
            catch { RuntimeName = manager.activeLoader.name; }

            // Spectator: show the left eye on the laptop window.
            XRSettings.gameViewRenderMode = GameViewRenderMode.LeftEye;
            Debug.Log("[SKYFOLD] XR running. Runtime: " + RuntimeName + ", device: " + XRSettings.loadedDeviceName +
                      ", eye texture " + XRSettings.eyeTextureWidth + "x" + XRSettings.eyeTextureHeight +
                      ", refresh " + (display.TryGetDisplayRefreshRate(out float hz) ? hz.ToString("0") + " Hz" : "unknown"));
            SetState(XRState.Running);
        }

        void Fail(string reason)
        {
            LastError = reason;
            Debug.LogWarning("[SKYFOLD] XR start failed: " + reason + " (log: " + Application.consoleLogPath + ")");
            SetState(XRState.Failed);
        }

        public void StopXR()
        {
            var manager = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            if (manager == null || manager.activeLoader == null) { SetState(XRState.Off); return; }
            SetState(XRState.Stopping);
            manager.StopSubsystems();
            manager.DeinitializeLoader();
            Debug.Log("[SKYFOLD] XR stopped.");
            SetState(XRState.Off);
        }

        public float RefreshRate
        {
            get
            {
                var manager = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
                var display = manager != null && manager.activeLoader != null ? manager.activeLoader.GetLoadedSubsystem<XRDisplaySubsystem>() : null;
                return display != null && display.TryGetDisplayRefreshRate(out float hz) ? hz : 0f;
            }
        }

        void Update()
        {
            if (State != XRState.Running) return;
            var head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (head.isValid && head.TryGetFeatureValue(CommonUsages.userPresence, out bool present)) UserPresent = present;
            else UserPresent = true;

            var left = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            var right = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            LeftTracked = left.isValid && (!left.TryGetFeatureValue(CommonUsages.isTracked, out bool lt) || lt);
            RightTracked = right.isValid && (!right.TryGetFeatureValue(CommonUsages.isTracked, out bool rt) || rt);
            ControllersTracked = LeftTracked && RightTracked;
        }

        void OnApplicationQuit()
        {
            if (State == XRState.Running) StopXR();
        }
    }
}
