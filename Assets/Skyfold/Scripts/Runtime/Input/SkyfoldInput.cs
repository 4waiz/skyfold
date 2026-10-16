using UnityEngine;
using UnityEngine.InputSystem;

namespace Skyfold
{
    /// <summary>
    /// Game action maps, defined in code so they are reproducible and version-controlled.
    /// XR locomotion, grabbing and UI rays come from the XRI Starter Assets actions; this asset
    /// holds the game's own actions (fold, objectives, pause, back, driving, desktop play).
    /// </summary>
    public static class SkyfoldInput
    {
        public const string MapGlobal = "Global";
        public const string MapDesktop = "Desktop";
        public const string MapArchitect = "DesktopArchitect";
        public const string MapDriving = "Driving";
        public const string MapVR = "VR";
        public const string MapDebug = "Debug";

        const string LeftHand = "<XRController>{LeftHand}";
        const string RightHand = "<XRController>{RightHand}";

        public static InputActionAsset Create()
        {
            var asset = ScriptableObject.CreateInstance<InputActionAsset>();
            asset.name = "SkyfoldControls";

            // Always on (except where the router disables them): pause and objectives.
            var global = asset.AddActionMap(MapGlobal);
            var pause = global.AddAction("Pause", InputActionType.Button);
            pause.AddBinding("<Keyboard>/escape");
            pause.AddBinding(LeftHand + "/{MenuButton}"); // Touch / Touch Plus left menu button
            pause.AddBinding("<Gamepad>/start");
            var objectives = global.AddAction("Objectives", InputActionType.Button);
            objectives.AddBinding("<Keyboard>/tab");
            objectives.AddBinding(LeftHand + "/{SecondaryButton}"); // Y
            var back = global.AddAction("Back", InputActionType.Button);
            back.AddBinding(RightHand + "/{SecondaryButton}"); // B
            back.AddBinding("<Keyboard>/backspace");

            // Desktop on foot.
            var desk = asset.AddActionMap(MapDesktop);
            var move = desk.AddAction("Move", InputActionType.Value, expectedControlLayout: "Vector2");
            move.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w").With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a").With("Right", "<Keyboard>/d");
            move.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/upArrow").With("Down", "<Keyboard>/downArrow")
                .With("Left", "<Keyboard>/leftArrow").With("Right", "<Keyboard>/rightArrow");
            desk.AddAction("Look", InputActionType.Value, "<Mouse>/delta", expectedControlLayout: "Vector2");
            desk.AddAction("Interact", InputActionType.Button, "<Keyboard>/e");
            desk.AddAction("Fold", InputActionType.Button, "<Keyboard>/q");
            desk.AddAction("Walk", InputActionType.Button, "<Keyboard>/leftShift");

            // Desktop at the plinth (architect camera, cursor free).
            var arch = asset.AddActionMap(MapArchitect);
            var orbit = arch.AddAction("Orbit", InputActionType.Value, expectedControlLayout: "Vector2");
            orbit.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w").With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a").With("Right", "<Keyboard>/d");
            arch.AddAction("Point", InputActionType.Value, "<Mouse>/position", expectedControlLayout: "Vector2");
            arch.AddAction("Drag", InputActionType.Button, "<Mouse>/leftButton");
            arch.AddAction("OrbitDrag", InputActionType.Button, "<Mouse>/rightButton");
            arch.AddAction("MouseDelta", InputActionType.Value, "<Mouse>/delta", expectedControlLayout: "Vector2");
            arch.AddAction("Zoom", InputActionType.Value, "<Mouse>/scroll/y", expectedControlLayout: "Axis");
            arch.AddAction("Rotate", InputActionType.Button, "<Keyboard>/r");
            arch.AddAction("Fold", InputActionType.Button, "<Keyboard>/q");

            // Driving (desktop and VR share the map; XR locomotion is disabled while driving).
            var drive = asset.AddActionMap(MapDriving);
            var steer = drive.AddAction("Steer", InputActionType.Value, expectedControlLayout: "Axis");
            steer.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/a").With("Positive", "<Keyboard>/d");
            steer.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/leftArrow").With("Positive", "<Keyboard>/rightArrow");
            steer.AddBinding(LeftHand + "/{Primary2DAxis}/x");
            var throttle = drive.AddAction("Throttle", InputActionType.Value, expectedControlLayout: "Axis");
            throttle.AddBinding("<Keyboard>/w");
            throttle.AddBinding("<Keyboard>/upArrow");
            throttle.AddBinding(RightHand + "/{Trigger}");
            var brake = drive.AddAction("Brake", InputActionType.Value, expectedControlLayout: "Axis");
            brake.AddBinding("<Keyboard>/s");
            brake.AddBinding("<Keyboard>/downArrow");
            brake.AddBinding(LeftHand + "/{Trigger}");
            drive.AddAction("Handbrake", InputActionType.Button, "<Keyboard>/space");
            var exit = drive.AddAction("Exit", InputActionType.Button);
            exit.AddBinding("<Keyboard>/e");
            exit.AddBinding(RightHand + "/{SecondaryButton}"); // B
            var horn = drive.AddAction("Horn", InputActionType.Button);
            horn.AddBinding("<Keyboard>/h");
            horn.AddBinding(RightHand + "/{PrimaryButton}"); // A is free while driving
            drive.AddAction("CameraToggle", InputActionType.Button, "<Keyboard>/c");

            // VR game actions on top of XRI (fold on X, trigger "use" on hovered world objects).
            var vr = asset.AddActionMap(MapVR);
            vr.AddAction("Fold", InputActionType.Button, LeftHand + "/{PrimaryButton}"); // X
            vr.AddAction("UseRight", InputActionType.Button, RightHand + "/{TriggerButton}");
            vr.AddAction("UseLeft", InputActionType.Button, LeftHand + "/{TriggerButton}");
            vr.AddAction("GripRight", InputActionType.Value, RightHand + "/{Grip}", expectedControlLayout: "Axis");
            vr.AddAction("GripLeft", InputActionType.Value, LeftHand + "/{Grip}", expectedControlLayout: "Axis");

            // Developer helpers (also used by QA screenshots).
            var dbg = asset.AddActionMap(MapDebug);
            dbg.AddAction("Diagnostics", InputActionType.Button, "<Keyboard>/f1");
            dbg.AddAction("Screenshot", InputActionType.Button, "<Keyboard>/f12");
            dbg.AddAction("OperatorReset", InputActionType.Button, "<Keyboard>/f5");

            return asset;
        }
    }
}
