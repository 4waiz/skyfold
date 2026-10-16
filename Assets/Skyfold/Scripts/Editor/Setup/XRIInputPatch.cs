using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Adapts the project's copy of the XRI Starter Assets input actions to SKYFOLD's Quest scheme:
    /// hold A to aim a teleport (release to jump), left stick only moves, right stick only turns,
    /// and the Starter "Jump" on A is removed. Action IDs are kept so prefab references stay valid.
    /// </summary>
    public static class XRIInputPatch
    {
        public const string AssetPath = "Assets/Samples/XR Interaction Toolkit/3.6.0/Starter Assets/XRI Default Input Actions.inputactions";
        const string RightA = "<XRController>{RightHand}/{PrimaryButton}";

        [MenuItem("SKYFOLD/Setup/Patch XRI Input Actions")]
        public static bool Patch()
        {
            if (!File.Exists(AssetPath)) { Debug.LogError("[SKYFOLD] Missing " + AssetPath); return false; }
            var asset = InputActionAsset.FromJson(File.ReadAllText(AssetPath));

            var rightTeleport = asset.FindAction("XRI Right Locomotion/Teleport Mode", true);
            bool already = rightTeleport.type == InputActionType.Button && rightTeleport.bindings.Count == 1 && rightTeleport.bindings[0].path == RightA;
            if (already) { Debug.Log("[SKYFOLD] XRI input actions already patched."); return true; }

            var typeField = typeof(InputAction).GetField("m_Type", BindingFlags.Instance | BindingFlags.NonPublic);
            typeField.SetValue(rightTeleport, InputActionType.Button);
            rightTeleport.expectedControlType = "Button";
            EraseAll(rightTeleport);
            rightTeleport.AddBinding(RightA);

            EraseAll(asset.FindAction("XRI Left Locomotion/Teleport Mode", true));
            EraseAll(asset.FindAction("XRI Left Locomotion/Turn", true));
            EraseAll(asset.FindAction("XRI Left Locomotion/Snap Turn", true));
            EraseAll(asset.FindAction("XRI Right Locomotion/Move", true));
            EraseAll(asset.FindAction("XRI Right Locomotion/Jump", true));
            EraseAll(asset.FindAction("XRI Left Locomotion/Grab Move", true));
            EraseAll(asset.FindAction("XRI Right Locomotion/Grab Move", true));

            File.WriteAllText(AssetPath, asset.ToJson());
            AssetDatabase.ImportAsset(AssetPath, ImportAssetOptions.ForceUpdate);
            Debug.Log("[SKYFOLD] Patched XRI input actions: A = teleport, left stick = move, right stick = turn, Jump removed.");
            return true;
        }

        static void EraseAll(InputAction action)
        {
            int guard = 64;
            while (action.bindings.Count > 0 && guard-- > 0) action.ChangeBinding(0).Erase();
        }
    }
}
