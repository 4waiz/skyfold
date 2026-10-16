using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using UnityEngine.XR.Interaction.Toolkit.Locomotion;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Comfort;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Turning;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        public const string StarterRig = "Assets/Samples/XR Interaction Toolkit/3.6.0/Starter Assets/Prefabs/XR Origin (XR Rig).prefab";
        public const string StarterVignette = "Assets/Samples/XR Interaction Toolkit/3.6.0/Starter Assets/TunnelingVignette/TunnelingVignette.prefab";

        static void SetupCamera(Camera cam, float near)
        {
            cam.nearClipPlane = near;
            cam.farClipPlane = 2200f;
            cam.allowMSAA = true;
            cam.allowHDR = true;
            var data = cam.GetUniversalAdditionalCameraData();
            data.renderPostProcessing = true;
            data.antialiasing = AntialiasingMode.None;
            data.renderShadows = true;
        }

        static void BuildRigs(Ctx c)
        {
            var start = c.Layout.GetAnchor("atelier.player");

            // ---------------- desktop
            var desk = Child(c.Rigs, "Desktop Player", start.Position, start.Yaw);
            SetLayer(desk, "PlayerBody", false);
            var cc = desk.AddComponent<CharacterController>();
            cc.height = 1.75f;
            cc.radius = 0.3f;
            cc.center = new Vector3(0f, 0.875f, 0f);
            cc.stepOffset = 0.4f;
            cc.slopeLimit = 50f;
            var head = Child(desk.transform, "Head", new Vector3(0f, 1.62f, 0f));
            var camGo = Child(head.transform, "Desktop Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 70f;
            SetupCamera(cam, 0.03f);
            camGo.AddComponent<AudioListener>();
            var dp = desk.AddComponent<DesktopPlayer>();
            dp.cam = cam;
            dp.head = head.transform;
            dp.plinthFocus = c.PlinthTop;
            dp.titleFocus = c.PlinthTop;
            var scan = desk.AddComponent<DesktopInteractionScanner>();
            scan.player = dp;
            scan.mask = ~LayerMask.GetMask("MiniCity", "PlayerBody", "Water");
            var tdi = desk.AddComponent<TabletopDesktopInput>();
            tdi.player = dp;
            tdi.pieceMask = LayerMask.GetMask("Interactable");
            c.Desktop = dp;

            // ---------------- VR (XRI Starter Assets rig)
            var vrRoot = Child(c.Rigs, "VR Rig");
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(StarterRig);
            if (prefab == null) throw new System.InvalidOperationException("XRI Starter Assets rig missing: " + StarterRig);
            var originGo = (GameObject)PrefabUtility.InstantiatePrefab(prefab, vrRoot.transform);
            originGo.transform.position = start.Position;
            originGo.transform.rotation = Quaternion.Euler(0f, start.Yaw, 0f);
            SetLayer(originGo, "PlayerBody", false);
            var vr = vrRoot.AddComponent<VRRigController>();
            vr.origin = originGo.GetComponent<Unity.XR.CoreUtils.XROrigin>();
            var xrCam = vr.origin.Camera;
            SetupCamera(xrCam, 0.02f);

            // Comfort vignette from the Starter Assets, driven by move/turn and the car.
            var vigPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(StarterVignette);
            if (vigPrefab != null)
            {
                var vig = (GameObject)PrefabUtility.InstantiatePrefab(vigPrefab, xrCam.transform);
                vig.transform.localPosition = Vector3.zero;
                var tvc = vig.GetComponentInChildren<TunnelingVignetteController>();
                if (tvc != null)
                {
                    var list = new List<LocomotionVignetteProvider>();
                    foreach (var p in originGo.GetComponentsInChildren<LocomotionProvider>(true))
                        if (p is ContinuousMoveProvider || p is ContinuousTurnProvider)
                            list.Add(new LocomotionVignetteProvider { locomotionProvider = p, enabled = true });
                    tvc.locomotionVignetteProviders = list;
                }
            }

            // Courier gloves replace the generic controller meshes.
            foreach (var side in new[] { "Left", "Right" })
            {
                var controller = FindDeep(originGo.transform, side + " Controller");
                var visual = FindDeep(originGo.transform, side + " Controller Visual");
                if (controller == null) continue;
                // The glove root is the grip point with the handle along its +Y (thumb up). The OpenXR grip
                // pose runs the handle along +Z (little finger to thumb), so tip the glove 90 deg about X.
                var glove = ModelLibrary.Spawn(side == "Left" ? "glove_L" : "glove_R", controller, Vector3.zero);
                if (ModelLibrary.Has(side == "Left" ? "glove_L" : "glove_R")) glove.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
                else glove.transform.localPosition = new Vector3(0f, -0.025f, -0.085f);
                glove.name = "Courier Glove " + side;
                var anim = glove.AddComponent<GloveAnimator>();
                anim.hand = side == "Left" ? Hand.Left : Hand.Right;
                var open = FindDeep(glove.transform, "Open");
                var grip = FindDeep(glove.transform, "Grip");
                anim.open = open != null ? open.gameObject : null;
                anim.grip = grip != null ? grip.gameObject : null;
                if (anim.grip != null) anim.grip.SetActive(false);
                if (visual != null && ModelLibrary.Has(side == "Left" ? "glove_L" : "glove_R")) visual.gameObject.SetActive(false);
                if (side == "Left") c.Atrium = FindDeep(glove.transform, "ANCHOR_wristui");
            }

            var use = vrRoot.AddComponent<VRUseHandler>();
            use.rig = vr;
            c.VR = vr;
            vrRoot.SetActive(false);
        }
    }
}
