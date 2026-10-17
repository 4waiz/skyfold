using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Essential scene/reference/settings validation. Writes Logs/validation.txt and returns the
    /// number of problems (0 = everything checked passed).
    /// </summary>
    public static class ProjectValidator
    {
        [MenuItem("SKYFOLD/Validate Project")]
        public static void Menu() => Validate(true);

        public static void Batch()
        {
            int n = Validate(true);
            EditorApplication.Exit(n == 0 ? 0 : 2);
        }

        public static int Validate(bool openScene)
        {
            var sb = new StringBuilder();
            int problems = 0;
            void Ok(bool ok, string what)
            {
                sb.AppendLine((ok ? "PASS  " : "FAIL  ") + what);
                if (!ok) problems++;
            }

            // Scene and wiring.
            Ok(File.Exists(SceneBuilder.ScenePath), "scene exists: " + SceneBuilder.ScenePath);
            Ok(EditorBuildSettings.scenes.Any(s => s.path == SceneBuilder.ScenePath && s.enabled), "scene is in build settings");
            if (openScene && File.Exists(SceneBuilder.ScenePath))
            {
                EditorSceneManager.OpenScene(SceneBuilder.ScenePath, OpenSceneMode.Single);
                var roots = Object.FindObjectsByType<GameRoot>(FindObjectsInactive.Include);
                Ok(roots.Length == 1, "exactly one GameRoot");
                if (roots.Length == 1)
                {
                    foreach (var f in typeof(GameRoot).GetFields(BindingFlags.Public | BindingFlags.Instance))
                    {
                        var v = f.GetValue(roots[0]);
                        bool ok = v != null && !(v is Object o && o == null);
                        if (v is System.Collections.IList list) ok = list.Count > 0;
                        Ok(ok, "GameRoot." + f.Name + " assigned");
                    }
                }
                var hud = Object.FindObjectsByType<HUDController>(FindObjectsInactive.Include).FirstOrDefault();
                Ok(hud != null && hud.noorPortrait != null, "HUD has Noor's radio badge sprite (Art/Images/noor_badge.png)");
                var listeners = Object.FindObjectsByType<AudioListener>(FindObjectsInactive.Include);
                Ok(listeners.Length == 2, $"two audio listeners exist (desktop + VR rig, only one active at a time): {listeners.Length}");
                var slots = Object.FindObjectsByType<FullScaleSlot>(FindObjectsInactive.Include);
                Ok(slots.Length == CityLayout.NacreBay.Sockets.Count * 2, $"full-scale + miniature slots for every socket ({slots.Length})");
                var sockets = Object.FindObjectsByType<TileSocket>(FindObjectsInactive.Include);
                Ok(sockets.Length == CityLayout.NacreBay.Sockets.Count, $"miniature socket per socket ({sockets.Length})");
                var pieces = Object.FindObjectsByType<ModulePiece>(FindObjectsInactive.Include);
                foreach (var id in new[] { "piece.bridge", "piece.corner", "piece.straight", "piece.link.tee", "piece.link.corner", "piece.link.straight" })
                    Ok(pieces.Any(p => p.pieceId == id), "piece exists: " + id);
                foreach (var m in new[] { MissionCatalog.Episode1, MissionCatalog.Episode2, MissionCatalog.Episode3, MissionCatalog.Demo })
                {
                    var def = MissionCatalog.Get(m);
                    foreach (var p in def.Inventory) Ok(pieces.Any(x => x.pieceId == p.Id), $"{m}: inventory piece {p.Id} has a scene object");
                    foreach (var o in def.Objectives)
                    {
                        if (string.IsNullOrEmpty(o.GuideTarget) || o.GuideTarget.Contains("nearest") || o.GuideTarget.Contains("next") || o.GuideTarget == "route.island") continue;
                        bool found = Object.FindObjectsByType<NamedTarget>(FindObjectsInactive.Include).Any(t => t.targetName == o.GuideTarget);
                        Ok(found, $"{m}: guide target '{o.GuideTarget}' for {o.Id} exists");
                    }
                }
            }

            // Player / input / XR settings.
            var ps = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset").FirstOrDefault();
            if (ps != null)
            {
                var so = new SerializedObject(ps);
                Ok(so.FindProperty("activeInputHandler").intValue == 1, "Active input handling = Input System only");
            }
            var general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Standalone);
            Ok(general != null && general.Manager != null && general.Manager.activeLoaders.Any(l => l is OpenXRLoader), "Standalone XR uses the OpenXR loader");
            Ok(general != null && !general.InitManagerOnStart, "XR is not initialised on startup (desktop first)");
            var ox = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone);
            Ok(ox != null && ox.renderMode == OpenXRSettings.RenderMode.SinglePassInstanced, "OpenXR single-pass instanced");
            Ok(ox != null && ox.GetFeature<OculusTouchControllerProfile>() != null && ox.GetFeature<OculusTouchControllerProfile>().enabled, "Oculus Touch profile enabled (Standalone)");
            Ok(ox != null && ox.GetFeature<MetaQuestTouchPlusControllerProfile>() != null && ox.GetFeature<MetaQuestTouchPlusControllerProfile>().enabled, "Meta Quest Touch Plus profile enabled (Standalone)");

            var xri = AssetDatabase.LoadAssetAtPath<InputActionAsset>(XRIInputPatch.AssetPath);
            var tp = xri != null ? xri.FindAction("XRI Right Locomotion/Teleport Mode") : null;
            Ok(tp != null && tp.bindings.Count == 1 && tp.bindings[0].path.Contains("PrimaryButton"), "XRI teleport is on A (hold to aim, release to jump)");
            var jump = xri != null ? xri.FindAction("XRI Right Locomotion/Jump") : null;
            Ok(jump != null && jump.bindings.Count == 0, "XRI jump removed from A");

            // Game action bindings exist for every documented control.
            var game = SkyfoldInput.Create();
            string[] required = { "Global/Pause", "Global/Objectives", "Global/Back", "Desktop/Move", "Desktop/Interact", "Desktop/Fold", "DesktopArchitect/Rotate", "DesktopArchitect/Drag", "Driving/Steer", "Driving/Throttle", "Driving/Brake", "Driving/Exit", "Driving/Handbrake", "Driving/ResetCar", "VR/Fold", "VR/UseRight" };
            foreach (var r in required) { var a = game.FindAction(r); Ok(a != null && a.bindings.Count > 0, "binding: " + r); }
            Object.DestroyImmediate(game);

            // Fonts.
            var heading = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(FontSetup.HeadingAsset);
            var body = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(FontSetup.BodyAsset);
            Ok(heading != null && body != null, "TextMeshPro font assets exist");
            if (heading != null && body != null) Ok(FontSetup.CheckCoverage(heading, body) == 0, "no missing glyphs in UI and caption strings");

            // Audio: every caption line has a clip (missing ones fall back to timed captions).
            var lib = AssetDatabase.LoadAssetAtPath<AudioLibrary>(AudioSetup.LibraryPath);
            Ok(lib != null && lib.entries.Count > 0, "audio library built");
            var vo = AssetDatabase.LoadAssetAtPath<TextAsset>("Assets/Skyfold/Resources/Dialogue/vo_lines.json");
            if (lib != null && vo != null)
            {
                var ids = System.Text.RegularExpressions.Regex.Matches(vo.text, "\"id\"\\s*:\\s*\"([^\"]+)\"").Cast<System.Text.RegularExpressions.Match>().Select(m => m.Groups[1].Value).ToList();
                var missing = ids.Where(id => !lib.Has(id)).ToList();
                Ok(missing.Count == 0, $"voice clip for every caption ({ids.Count - missing.Count}/{ids.Count})" + (missing.Count > 0 ? " missing: " + string.Join(", ", missing) : ""));
                foreach (var sfx in new[] { "socket_snap", "socket_reject", "bridge_assemble", "fold_in", "fold_out", "car_motor_loop", "plane_idle_loop", "music_menu_loop", "music_finale", "amb_coast_loop" })
                    Ok(lib.Has(sfx), "audio clip: " + sfx);
            }

            // Road model openings agree with the rules.
            foreach (ModuleType t in System.Enum.GetValues(typeof(ModuleType)))
            {
                if (t == ModuleType.None) continue;
                var prefab = ModelLibrary.Prefab(ModuleInfo.ModelName(t));
                if (prefab == null) { Ok(false, "model for " + t); continue; }
                var road = ModelInspector.SubmeshBounds(prefab, "SKY_Road");
                if (!road.HasValue) { Ok(false, "road surface in " + t); continue; }
                var b = road.Value;
                DirMask m = DirMask.None;
                if (b.max.z > 7.6f) m |= DirMask.N;
                if (b.max.x > 7.6f) m |= DirMask.E;
                if (b.min.z < -7.6f) m |= DirMask.S;
                if (b.min.x < -7.6f) m |= DirMask.W;
                Ok(m == ModuleInfo.BaseOpenings(t), $"{t} model openings {m} match rules {ModuleInfo.BaseOpenings(t)}");
            }

            if (ModelLibrary.Missing.Count > 0) sb.AppendLine("INFO  placeholders used for: " + string.Join(", ", ModelLibrary.Missing));
            sb.Insert(0, $"SKYFOLD validation: {problems} problem(s)\n");
            Directory.CreateDirectory("Logs");
            File.WriteAllText("Logs/validation.txt", sb.ToString());
            Debug.Log("[SKYFOLD] Validation: " + problems + " problem(s). See Logs/validation.txt");
            return problems;
        }
    }
}
