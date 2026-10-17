using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;

namespace Skyfold
{
    /// <summary>
    /// "vrsim": the headset path without a headset. Simulated HMD and Quest-style controllers (separate grip and aim
    /// poses, every button the game binds, by usage like the OpenXR Touch profile) drive the real VR rig, so the
    /// gloves, the button cards, the bindings, folding, walking, turning, driving and pausing are all exercised.
    /// What it cannot cover: the real runtime's poses, tracking, comfort and rendering in the headset.
    /// </summary>
    public sealed partial class QARunner
    {
        const string SimControllerLayout = @"{
            ""name"": ""SkyfoldSimController"",
            ""extend"": ""XRController"",
            ""controls"": [
                { ""name"": ""pointerPosition"", ""layout"": ""Vector3"" },
                { ""name"": ""pointerRotation"", ""layout"": ""Quaternion"" },
                { ""name"": ""thumbstick"", ""layout"": ""Stick"", ""usage"": ""Primary2DAxis"", ""format"": ""VEC2"" },
                { ""name"": ""trigger"", ""layout"": ""Axis"", ""usage"": ""Trigger"", ""format"": ""FLT"" },
                { ""name"": ""grip"", ""layout"": ""Axis"", ""usage"": ""Grip"", ""format"": ""FLT"" },
                { ""name"": ""triggerPressed"", ""layout"": ""Button"", ""usage"": ""TriggerButton"", ""format"": ""FLT"" },
                { ""name"": ""gripPressed"", ""layout"": ""Button"", ""usage"": ""GripButton"", ""format"": ""FLT"" },
                { ""name"": ""primaryButton"", ""layout"": ""Button"", ""usage"": ""PrimaryButton"", ""format"": ""FLT"" },
                { ""name"": ""secondaryButton"", ""layout"": ""Button"", ""usage"": ""SecondaryButton"", ""format"": ""FLT"" },
                { ""name"": ""menuButton"", ""layout"": ""Button"", ""usage"": ""MenuButton"", ""format"": ""FLT"" },
                { ""name"": ""thumbstickClicked"", ""layout"": ""Button"", ""usage"": ""Primary2DAxisClick"", ""format"": ""FLT"" }
            ]
        }";

        UnityEngine.InputSystem.InputDevice m_SimHmd, m_SimLeft, m_SimRight;
        bool m_SimPoses;
        float m_SimPitch;                     // head pitch, degrees down
        const float SimEye = 1.62f;
        const float AimTilt = 55f;            // the aim pose points along the controller, about 55 deg below the handle

        /// <summary>Natural hold in tracking space: hands in front of the chest, handle tilted 35 deg forward,
        /// wrists turned 12 deg inward. Returns the OpenXR grip pose (+Z handle toward the thumb, +Y toward the wrist).</summary>
        static void SimGrip(bool left, out Vector3 pos, out Quaternion rot)
        {
            pos = new Vector3(left ? -0.17f : 0.17f, SimEye - 0.34f, 0.36f);
            var canonical = Quaternion.LookRotation(Vector3.up, Vector3.back); // handle vertical, thumb up, palm across
            rot = Quaternion.Euler(0f, left ? 12f : -12f, 0f) * Quaternion.Euler(35f, 0f, 0f) * canonical;
        }

        void SimDevices()
        {
            InputSystem.RegisterLayout(SimControllerLayout);
            m_SimHmd = InputSystem.AddDevice<XRHMD>("Sim HMD");
            m_SimLeft = InputSystem.AddDevice("SkyfoldSimController", "Sim Left");
            InputSystem.SetDeviceUsage(m_SimLeft, UnityEngine.InputSystem.CommonUsages.LeftHand);
            m_SimRight = InputSystem.AddDevice("SkyfoldSimController", "Sim Right");
            InputSystem.SetDeviceUsage(m_SimRight, UnityEngine.InputSystem.CommonUsages.RightHand);
            Log($"simulated devices: {m_SimHmd.layout}, {m_SimLeft.layout} x2");
        }

        void SimRemoveDevices()
        {
            foreach (var d in new[] { m_SimHmd, m_SimLeft, m_SimRight })
                if (d != null && d.added) InputSystem.RemoveDevice(d);
        }

        IEnumerator SimPoseLoop()
        {
            while (m_SimPoses)
            {
                var head = Quaternion.Euler(m_SimPitch, 0f, 0f);
                var eye = new Vector3(0f, SimEye, 0f);
                InputSystem.QueueDeltaStateEvent(m_SimHmd["centerEyePosition"], eye);
                InputSystem.QueueDeltaStateEvent(m_SimHmd["centerEyeRotation"], head);
                InputSystem.QueueDeltaStateEvent(m_SimHmd["devicePosition"], eye);
                InputSystem.QueueDeltaStateEvent(m_SimHmd["deviceRotation"], head);
                InputSystem.QueueDeltaStateEvent(m_SimHmd["trackingState"], 3);
                foreach (var left in new[] { true, false })
                {
                    var d = left ? m_SimLeft : m_SimRight;
                    SimGrip(left, out var p, out var r);
                    var aim = r * Quaternion.Euler(AimTilt, 0f, 0f);
                    InputSystem.QueueDeltaStateEvent(d["devicePosition"], p);
                    InputSystem.QueueDeltaStateEvent(d["deviceRotation"], r);
                    InputSystem.QueueDeltaStateEvent(d["pointerPosition"], p + r * new Vector3(0f, -0.03f, 0.05f));
                    InputSystem.QueueDeltaStateEvent(d["pointerRotation"], aim);
                    InputSystem.QueueDeltaStateEvent(d["trackingState"], 3);
                }
                yield return null;
            }
        }

        void SimSet(UnityEngine.InputSystem.InputDevice d, string control, float v) => InputSystem.QueueDeltaStateEvent(d[control], v);
        void SimStick(UnityEngine.InputSystem.InputDevice d, Vector2 v) => InputSystem.QueueDeltaStateEvent(d["thumbstick"], v);

        IEnumerator SimPress(UnityEngine.InputSystem.InputDevice d, string control, float hold = 0.15f)
        {
            SimSet(d, control, 1f);
            yield return new WaitForSecondsRealtime(hold);
            SimSet(d, control, 0f);
            yield return null;
            yield return null;
        }

        IEnumerator SimLook(float pitch)
        {
            m_SimPitch = pitch;
            yield return new WaitForSecondsRealtime(0.6f);
        }

        IEnumerator VRSim()
        {
            SimDevices();
            m_SimPoses = true;
            StartCoroutine(SimPoseLoop());
            yield return null;
            Root.EnterSimulatedVRForQA();
            yield return new WaitForSecondsRealtime(1f);
            var rigs = PlayerRigs.Instance;
            var vr = rigs.vr;
            var input = InputRouter.Instance;
            Check(rigs.Mode == PlayMode.VR && input.Mode == PlayMode.VR, "VR rig active with a simulated headset");

            Root.StartMission(MissionCatalog.Demo);
            yield return new WaitForSecondsRealtime(1.5f);
            Check(input.Context == InputContext.Architect && FoldController.Instance.InAtelier, "the Atelier in VR is the Architect context");

            // Gloves ride the GRIP pose; the XRI controller transforms ride the AIM pose (pointer first).
            var hints = vr.GetComponent<ControllerHints>();
            Check(hints != null && hints.leftAnchor != null && hints.rightAnchor != null, "button cards and glove anchors exist");
            if (hints == null || hints.leftAnchor == null) yield break;
            foreach (var left in new[] { true, false })
            {
                var anchor = left ? hints.leftAnchor : hints.rightAnchor;
                var controller = left ? vr.LeftHand : vr.RightHand;
                SimGrip(left, out var gp, out var gr);
                Vector3 want = anchor.parent.TransformPoint(gp);
                float off = Vector3.Distance(anchor.position, want);
                float ang = Quaternion.Angle(anchor.rotation, anchor.parent.rotation * gr);
                float aimGap = Quaternion.Angle(anchor.rotation, controller.rotation);
                Check(off < 0.002f && ang < 0.5f, $"{(left ? "left" : "right")} glove follows the grip pose ({off * 1000f:0.0} mm, {ang:0.0} deg)");
                Check(aimGap > 40f, $"{(left ? "left" : "right")} XRI controller follows the aim pose, {aimGap:0} deg from the glove (why the old glove pointed wrong)");
                var glove = anchor.childCount > 0 ? anchor.GetChild(0) : null;
                Check(glove != null && glove.name.StartsWith("Courier Glove") && Quaternion.Angle(glove.localRotation, Quaternion.Euler(90f, 0f, 0f)) < 0.5f,
                      $"{(left ? "left" : "right")} glove sits on its anchor, handle along the grip pose");
            }

            // Look at your hands: both cards, with Grip lit for the grab step.
            yield return SimLook(32f);
            Check(hints.LeftVisible && hints.RightVisible, "button cards show when you look at your hands");
            string lit = hints.LitSummary();
            Check(lit.Contains("Left:Grip") && lit.Contains("Right:Grip"), "the grab step lights Grip on both hands (" + lit + ")");
            yield return Shot("vr_01_atelier_hands");
            yield return SimLook(6f);
            yield return Shot("vr_02_atelier_view");

            // Place the bridge, then fold down with X on the simulated left controller.
            yield return PlacePiece("piece.bridge", "bridge_east", 0);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "t.fold", 20f, "fold objective");
            yield return SimLook(32f);
            lit = hints.LitSummary();
            Check(lit.Contains("Left:X"), "the fold step lights X on the left hand (" + lit + ")");
            yield return Shot("vr_03_fold_hint");
            yield return SimPress(m_SimLeft, "primaryButton");
            yield return WaitUntil(() => FoldController.Instance.InStreet && !FoldController.Instance.Busy, 6f, "X folds down into the street (simulated controller)");
            yield return new WaitForSecondsRealtime(0.6f);
            Check(input.Context == InputContext.OnFoot, "on foot in the street");
            Check(hints.LeftVisible && hints.RightVisible, "the cards pop up when the controls change");
            yield return Shot("vr_04_street_hands");

            // Left stick walks, right stick snap-turns.
            yield return SimLook(0f);
            Vector3 p0 = vr.FeetPosition;
            Vector3 fwd = rigs.Forward;
            SimStick(m_SimLeft, Vector2.up);
            yield return new WaitForSecondsRealtime(1.5f);
            SimStick(m_SimLeft, Vector2.zero);
            yield return new WaitForSecondsRealtime(0.2f);
            float walked = Vector3.Dot(vr.FeetPosition - p0, fwd);
            Check(walked > 1f, $"left stick walks forward ({walked:0.0} m in 1.5 s)");
            float yaw0 = vr.Head.eulerAngles.y;
            SimStick(m_SimRight, Vector2.right);
            yield return new WaitForSecondsRealtime(0.35f);
            SimStick(m_SimRight, Vector2.zero);
            yield return new WaitForSecondsRealtime(0.4f);
            float turned = Mathf.DeltaAngle(yaw0, vr.Head.eulerAngles.y);
            Check(Mathf.Abs(turned - SettingsStore.Current.snapAngle) < 3f, $"right stick snap-turns right ({turned:0} deg)");

            // Into the car: the cards switch to driving, the right trigger drives, the left brakes, B climbs out.
            var car = CourierVehicle.Instance;
            rigs.TeleportTo(car.exitLeft.position, car.transform.eulerAngles.y + 90f);
            yield return new WaitForSecondsRealtime(0.3f);
            car.RequestEnter();
            yield return WaitUntil(() => car.HasDriver && !car.Busy, 5f, "seated in the car in VR");
            Check(input.Context == InputContext.Driving, "driving context");
            yield return SimLook(30f);
            lit = hints.LitSummary();
            Check(lit.Contains("Right:Trigger"), "in the car the right trigger (accelerate) is lit (" + lit + ")");
            yield return Shot("vr_05_car_hands");
            SimSet(m_SimRight, "trigger", 1f);
            SimSet(m_SimRight, "triggerPressed", 1f);
            yield return new WaitForSecondsRealtime(1.5f);
            float speed = car.Speed;
            SimSet(m_SimRight, "trigger", 0f);
            SimSet(m_SimRight, "triggerPressed", 0f);
            Check(speed > 1f, $"right trigger accelerates ({speed:0.0} m/s)");
            SimSet(m_SimLeft, "trigger", 1f);
            float t = 0f;
            while (Mathf.Abs(car.Speed) > 0.3f && t < 5f) { t += Time.unscaledDeltaTime; yield return null; }
            SimSet(m_SimLeft, "trigger", 0f);
            Check(Mathf.Abs(car.Speed) <= 0.3f, $"left trigger brakes to a stop ({car.Speed:0.0} m/s)");
            yield return new WaitForSecondsRealtime(0.3f);
            yield return SimPress(m_SimRight, "secondaryButton");
            yield return WaitUntil(() => !car.HasDriver && !car.Busy, 5f, "B climbs out of the stopped car");

            // Pause and resume from the left Menu button; the cards switch to "Trigger: select".
            yield return SimPress(m_SimLeft, "menuButton");
            yield return WaitUntil(() => Root.IsPaused, 2f, "left Menu button pauses");
            yield return SimLook(28f);
            lit = hints.LitSummary();
            Check(lit.Contains("Trigger"), "paused, the cards light Trigger (select) (" + lit + ")");
            yield return Shot("vr_06_pause_hands");
            yield return SimPress(m_SimLeft, "menuButton");
            yield return WaitUntil(() => !Root.IsPaused, 2f, "left Menu button resumes");

            m_SimPoses = false;
            yield return null;
            SimRemoveDevices();
        }
    }
}
