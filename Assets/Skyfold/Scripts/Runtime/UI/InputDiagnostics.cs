using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>
    /// Temporary input diagnostics: device/profile, both sticks, triggers, grips, face buttons,
    /// tracking and a haptics test (both grips + both triggers). Hidden unless --diagnostics is
    /// passed, F1 is pressed in a development build, or the Controls screen toggle is on.
    /// </summary>
    public sealed class InputDiagnostics : MonoBehaviour
    {
        Canvas m_Canvas, m_World;
        TextMeshProUGUI m_Text, m_WorldText;
        bool m_Visible;
        float m_NextHaptic;
        readonly StringBuilder m_Sb = new StringBuilder(2048);

        static readonly string[] ControlNames =
        {
            "thumbstick", "primary2DAxis", "trigger", "grip", "primaryButton", "secondaryButton",
            "menu", "thumbstickClicked", "primary2DAxisClick", "triggerPressed", "gripPressed", "isTracked", "trackingState"
        };

        void Awake()
        {
            m_Canvas = UIKit.ScreenCanvas("Diagnostics Canvas", 90, transform);
            m_Canvas.GetComponent<GraphicRaycaster>().enabled = false;
            var panel = UIKit.Panel(m_Canvas.transform, "Panel", new Color(0.08f, 0.12f, 0.14f, 0.9f), 18f, 4f, false);
            panel.anchorMin = panel.anchorMax = new Vector2(1f, 0.5f);
            panel.pivot = new Vector2(1f, 0.5f);
            panel.anchoredPosition = new Vector2(-24f, 0f);
            panel.sizeDelta = new Vector2(620f, 0f);
            m_Text = UIKit.Text(panel, "", 17f, UIStyle.Pearl);

            var wgo = new GameObject("Diagnostics World", typeof(RectTransform));
            wgo.transform.SetParent(transform, false);
            m_World = wgo.AddComponent<Canvas>();
            m_World.renderMode = RenderMode.WorldSpace;
            ((RectTransform)wgo.transform).sizeDelta = new Vector2(640f, 900f);
            wgo.transform.localScale = Vector3.one * 0.0007f;
            var wp = UIKit.Panel(wgo.transform, "Panel", new Color(0.08f, 0.12f, 0.14f, 0.92f), 18f, 4f, false);
            UIKit.Stretch(wp);
            m_WorldText = UIKit.Text(wp, "", 18f, UIStyle.Pearl);
            SetVisible(false);
        }

        public void SetVisible(bool v)
        {
            m_Visible = v;
            m_Canvas.gameObject.SetActive(v);
            m_World.gameObject.SetActive(v && PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.VR);
        }

        public void Toggle() => SetVisible(!m_Visible);

        void Update()
        {
            bool wanted = LaunchOptions.Current.Diagnostics || SettingsStore.Current.showDiagnostics;
            var input = InputRouter.Instance;
            if (input != null && input.Diagnostics.WasPressedThisFrame() && (Debug.isDebugBuild || wanted)) Toggle();
            else if (wanted && !m_Visible && Time.frameCount % 30 == 0) SetVisible(true);
            if (!m_Visible) return;

            m_Sb.Clear();
            var rigs = PlayerRigs.Instance;
            var xr = XRBootstrap.Instance;
            m_Sb.AppendLine("<b>INPUT DIAGNOSTICS</b>  (temporary, hidden in release)");
            m_Sb.AppendLine($"Mode: {(rigs != null ? rigs.Mode.ToString() : "-")}   Context: {(input != null ? input.Context.ToString() : "-")}");
            if (xr != null) m_Sb.AppendLine($"XR: {xr.State}  {xr.RuntimeName}  {(xr.RefreshRate > 0 ? xr.RefreshRate.ToString("0") + " Hz" : "")}\nUser present: {xr.UserPresent}   L tracked: {xr.LeftTracked}   R tracked: {xr.RightTracked}");
            Device("Left", XRController.leftHand);
            Device("Right", XRController.rightHand);
            var hmd = InputSystem.GetDevice<XRHMD>();
            m_Sb.AppendLine(hmd != null ? $"<color=#35E0D0>HMD</color> {hmd.layout} · {hmd.description.product}" : "HMD: none");
            if (Keyboard.current != null) m_Sb.AppendLine($"Keyboard: {Keyboard.current.displayName}   Mouse: {(Mouse.current != null ? Mouse.current.displayName : "none")}");
            m_Sb.AppendLine("Haptics test: hold both grips + both triggers.");

            string s = m_Sb.ToString();
            m_Text.text = s;
            m_WorldText.text = s;

            bool vr = rigs != null && rigs.Mode == PlayMode.VR;
            if (m_World.gameObject.activeSelf != vr) m_World.gameObject.SetActive(vr);
            if (vr && rigs.vr != null && rigs.vr.LeftHand != null)
            {
                var hand = rigs.vr.LeftHand;
                m_World.transform.position = hand.position + hand.up * 0.18f;
                m_World.transform.rotation = Quaternion.LookRotation(m_World.transform.position - rigs.Head.position);
                if (input != null && input.GripLeft.ReadValue<float>() > 0.8f && input.GripRight.ReadValue<float>() > 0.8f &&
                    input.UseLeft.IsPressed() && input.UseRight.IsPressed() && Time.unscaledTime > m_NextHaptic)
                {
                    m_NextHaptic = Time.unscaledTime + 0.6f;
                    rigs.vr.HapticBoth(0.6f, 0.2f);
                }
            }
        }

        void Device(string label, InputDevice d)
        {
            if (d == null) { m_Sb.AppendLine($"<color=#F2714B>{label}: not connected</color>"); return; }
            m_Sb.AppendLine($"<color=#35E0D0>{label}</color> {d.layout} · {d.description.product} {(d.enabled ? "" : "(disabled)")}");
            foreach (var n in ControlNames)
            {
                var c = d.TryGetChildControl(n);
                if (c == null) continue;
                object v;
                try { v = c.ReadValueAsObject(); } catch { v = "?"; }
                if (v is float f) v = f.ToString("0.00");
                else if (v is Vector2 v2) v = $"({v2.x:0.00}, {v2.y:0.00})";
                m_Sb.Append("   ").Append(n).Append(": ").Append(v).AppendLine();
            }
        }
    }
}
