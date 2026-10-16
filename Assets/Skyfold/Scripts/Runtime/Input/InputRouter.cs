using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Skyfold
{
    public enum InputContext { Menu, OnFoot, Architect, Driving, RemoteDriving, Cutscene, Paused, Results }

    /// <summary>
    /// Owns the game's action maps and keeps exactly one gameplay context active, so overlapping
    /// maps (walking vs driving vs dragging pieces) never fire together.
    /// </summary>
    public sealed class InputRouter : MonoBehaviour
    {
        public static InputRouter Instance { get; private set; }

        public InputActionAsset Asset { get; private set; }
        public InputContext Context { get; private set; } = InputContext.Menu;
        public PlayMode Mode { get; private set; } = PlayMode.Desktop;
        public event Action<InputContext> ContextChanged;

        InputActionMap m_Global, m_Desktop, m_Architect, m_Driving, m_VR, m_Debug;

        public InputAction Pause, Objectives, Back;
        public InputAction Move, Look, Interact, FoldDesktop, WalkSlow;
        public InputAction Orbit, Point, Drag, OrbitDrag, MouseDelta, Zoom, Rotate, FoldArchitect;
        public InputAction Steer, Throttle, Brake, Handbrake, Exit, Horn, CameraToggle, ResetCar;
        public InputAction FoldVR, UseRight, UseLeft, GripRight, GripLeft;
        public InputAction Diagnostics, Screenshot, OperatorReset;

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(this); return; }
            Instance = this;
            Asset = SkyfoldInput.Create();
            m_Global = Asset.FindActionMap(SkyfoldInput.MapGlobal, true);
            m_Desktop = Asset.FindActionMap(SkyfoldInput.MapDesktop, true);
            m_Architect = Asset.FindActionMap(SkyfoldInput.MapArchitect, true);
            m_Driving = Asset.FindActionMap(SkyfoldInput.MapDriving, true);
            m_VR = Asset.FindActionMap(SkyfoldInput.MapVR, true);
            m_Debug = Asset.FindActionMap(SkyfoldInput.MapDebug, true);

            Pause = m_Global["Pause"]; Objectives = m_Global["Objectives"]; Back = m_Global["Back"];
            Move = m_Desktop["Move"]; Look = m_Desktop["Look"]; Interact = m_Desktop["Interact"];
            FoldDesktop = m_Desktop["Fold"]; WalkSlow = m_Desktop["Walk"];
            Orbit = m_Architect["Orbit"]; Point = m_Architect["Point"]; Drag = m_Architect["Drag"];
            OrbitDrag = m_Architect["OrbitDrag"]; MouseDelta = m_Architect["MouseDelta"]; Zoom = m_Architect["Zoom"];
            Rotate = m_Architect["Rotate"]; FoldArchitect = m_Architect["Fold"];
            Steer = m_Driving["Steer"]; Throttle = m_Driving["Throttle"]; Brake = m_Driving["Brake"];
            Handbrake = m_Driving["Handbrake"]; Exit = m_Driving["Exit"]; Horn = m_Driving["Horn"];
            CameraToggle = m_Driving["CameraToggle"]; ResetCar = m_Driving["ResetCar"];
            FoldVR = m_VR["Fold"]; UseRight = m_VR["UseRight"]; UseLeft = m_VR["UseLeft"];
            GripRight = m_VR["GripRight"]; GripLeft = m_VR["GripLeft"];
            Diagnostics = m_Debug["Diagnostics"]; Screenshot = m_Debug["Screenshot"]; OperatorReset = m_Debug["OperatorReset"];

            m_Global.Enable();
            m_Debug.Enable();
            Apply();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            Asset?.Disable();
            if (Asset != null) Destroy(Asset);
        }

        public void SetMode(PlayMode mode)
        {
            Mode = mode;
            Apply();
        }

        public void SetContext(InputContext ctx)
        {
            if (ctx == Context) { Apply(); return; }
            Context = ctx;
            Apply();
            ContextChanged?.Invoke(ctx);
        }

        void Apply()
        {
            if (m_Desktop == null) return;
            m_Desktop.Disable();
            m_Architect.Disable();
            m_Driving.Disable();
            m_VR.Disable();
            bool vr = Mode == PlayMode.VR;
            switch (Context)
            {
                case InputContext.OnFoot:
                case InputContext.Cutscene:
                    if (vr) m_VR.Enable(); else m_Desktop.Enable();
                    break;
                case InputContext.Architect:
                    if (vr) m_VR.Enable(); else m_Architect.Enable();
                    break;
                case InputContext.Driving:
                case InputContext.RemoteDriving:
                    m_Driving.Enable();
                    break;
            }
            // Objectives toggle is meaningless in menus.
            if (Context == InputContext.Menu || Context == InputContext.Results) Objectives.Disable(); else Objectives.Enable();
        }

        public bool FoldPressedThisFrame()
        {
            if (Mode == PlayMode.VR) return FoldVR.WasPressedThisFrame();
            return Context == InputContext.Architect ? FoldArchitect.WasPressedThisFrame() : FoldDesktop.WasPressedThisFrame();
        }

        public string FoldKeyLabel => Mode == PlayMode.VR ? "X" : "Q";
        public string UseKeyLabel => Mode == PlayMode.VR ? "Trigger" : "E";
        public string ExitKeyLabel => Mode == PlayMode.VR ? "B" : "E";
        public string ResetCarKeyLabel => Mode == PlayMode.VR ? "X" : "R";
        public string ObjectivesKeyLabel => Mode == PlayMode.VR ? "Y" : "Tab";
        public string PauseKeyLabel => Mode == PlayMode.VR ? "Menu" : "Esc";
    }
}
