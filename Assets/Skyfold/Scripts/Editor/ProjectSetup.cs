using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.PackageManager.UI;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEditor.XR.OpenXR.Features;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Idempotent project configuration: player settings, URP quality, physics layers,
    /// XR Management (OpenXR, deferred start) and the XRI Starter Assets sample.
    /// Run from the SKYFOLD menu or in batch mode via BatchConfigure.
    /// </summary>
    public static class ProjectSetup
    {
        public const string UrpAssetPath = "Assets/Settings/PC_RPAsset.asset";
        public const string XRSettingsFolder = "Assets/XR";
        const string XriPackage = "com.unity.xr.interaction.toolkit";
        const string XriVersion = "3.6.0";

        public static readonly string[] Layers =
        {
            // index 8 onward
            "MiniCity", "Interactable", "Vehicle", "Water", "PlayerBody", "Ground", "WorldUI", "Trigger"
        };

        [MenuItem("SKYFOLD/Setup/Configure Project")]
        public static void ConfigureProject()
        {
            ConfigurePlayer();
            ConfigureLayers();
            ConfigureRendering();
            ConfigureXR();
            ImportStarterAssets();
            AssetDatabase.SaveAssets();
            Debug.Log("[SKYFOLD] Project configured.");
        }

        public static void BatchConfigure()
        {
            try
            {
                ConfigureProject();
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                EditorApplication.Exit(1);
            }
        }

        static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Team Kanban";
            PlayerSettings.productName = "SKYFOLD";
            PlayerSettings.bundleVersion = "0.9.0";
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone, "com.teamkanban.skyfold");
            PlayerSettings.colorSpace = ColorSpace.Linear;

            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[] { GraphicsDeviceType.Direct3D11 });
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);

            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.defaultIsNativeResolution = true;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.allowFullscreenSwitch = true;
            PlayerSettings.runInBackground = true;   // keep running while the headset has focus
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.forceSingleInstance = true; // two instances would fight over the XR runtime
            PlayerSettings.usePlayerLog = true;
            PlayerSettings.stereoRenderingPath = StereoRenderingPath.Instancing;

            PlayerSettings.SplashScreen.show = false;
            PlayerSettings.SplashScreen.showUnityLogo = false;

            // New Input System only.
            var playerSettings = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset").FirstOrDefault();
            if (playerSettings != null)
            {
                var so = new SerializedObject(playerSettings);
                var handler = so.FindProperty("activeInputHandler");
                if (handler != null && handler.intValue != 1)
                {
                    handler.intValue = 1;
                    so.ApplyModifiedPropertiesWithoutUndo();
                }
            }
        }

        static void ConfigureLayers()
        {
            var tagManager = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset").FirstOrDefault();
            if (tagManager == null) return;
            var so = new SerializedObject(tagManager);
            var layers = so.FindProperty("layers");
            for (int i = 0; i < Layers.Length; i++)
            {
                var element = layers.GetArrayElementAtIndex(8 + i);
                if (element.stringValue != Layers[i]) element.stringValue = Layers[i];
            }
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ConfigureRendering()
        {
            var urp = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(UrpAssetPath);
            if (urp == null)
                throw new InvalidOperationException("URP asset missing at " + UrpAssetPath);

            var so = new SerializedObject(urp);
            SetInt(so, "m_MSAA", 4);
            SetBool(so, "m_SupportsHDR", true);
            SetBool(so, "m_RequireDepthTexture", false);
            SetBool(so, "m_RequireOpaqueTexture", false);
            SetFloat(so, "m_RenderScale", 1f);
            SetInt(so, "m_MainLightShadowmapResolution", 4096);
            SetBool(so, "m_AdditionalLightShadowsSupported", false);
            SetInt(so, "m_AdditionalLightsPerObjectLimit", 4);
            SetFloat(so, "m_ShadowDistance", 120f);
            SetInt(so, "m_ShadowCascadeCount", 2);
            SetFloat(so, "m_Cascade2Split", 0.2f);
            SetBool(so, "m_SoftShadowsSupported", true);
            SetInt(so, "m_SoftShadowQuality", 2);
            SetBool(so, "m_UseSRPBatcher", true);
            SetBool(so, "m_UseAdaptivePerformance", false);
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(urp);

            GraphicsSettings.defaultRenderPipeline = urp;
            int current = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = urp;
                QualitySettings.vSyncCount = 1;
                QualitySettings.antiAliasing = 4;
                QualitySettings.anisotropicFiltering = AnisotropicFiltering.ForceEnable;
                QualitySettings.lodBias = 1.5f;
            }
            QualitySettings.SetQualityLevel(Math.Max(0, current), false);
        }

        static void ConfigureXR()
        {
            if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget) || perTarget == null)
            {
                var guids = AssetDatabase.FindAssets("t:XRGeneralSettingsPerBuildTarget");
                if (guids.Length > 0)
                    perTarget = AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(AssetDatabase.GUIDToAssetPath(guids[0]));
                if (perTarget == null)
                {
                    if (!AssetDatabase.IsValidFolder(XRSettingsFolder))
                        AssetDatabase.CreateFolder("Assets", "XR");
                    perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                    AssetDatabase.CreateAsset(perTarget, XRSettingsFolder + "/XRGeneralSettingsPerBuildTarget.asset");
                }
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }

            if (!perTarget.HasManagerSettingsForBuildTarget(BuildTargetGroup.Standalone))
                perTarget.CreateDefaultManagerSettingsForBuildTarget(BuildTargetGroup.Standalone);

            var general = perTarget.SettingsForBuildTarget(BuildTargetGroup.Standalone);
            general.InitManagerOnStart = false; // the player chooses Desktop or VR first
            var manager = general.Manager;
            bool hasOpenXR = manager.activeLoaders.Any(l => l is OpenXRLoader);
            if (!hasOpenXR)
            {
                bool ok = XRPackageMetadataStore.AssignLoader(manager, typeof(OpenXRLoader).FullName, BuildTargetGroup.Standalone);
                Debug.Log("[SKYFOLD] Assign OpenXR loader: " + ok);
            }
            EditorUtility.SetDirty(general);
            EditorUtility.SetDirty(manager);
            EditorUtility.SetDirty(perTarget);

            FeatureHelpers.RefreshFeatures(BuildTargetGroup.Standalone);
            var openxr = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone);
            if (openxr == null)
                throw new InvalidOperationException("OpenXR settings for Standalone are unavailable.");
            openxr.renderMode = OpenXRSettings.RenderMode.SinglePassInstanced;
            openxr.depthSubmissionMode = OpenXRSettings.DepthSubmissionMode.Depth24Bit;

            foreach (var feature in openxr.GetFeatures())
            {
                if (feature is OculusTouchControllerProfile || feature is MetaQuestTouchPlusControllerProfile)
                    feature.enabled = true;
            }
            EditorUtility.SetDirty(openxr);
            Debug.Log("[SKYFOLD] OpenXR Standalone: SinglePassInstanced, Touch + Touch Plus profiles enabled, InitManagerOnStart=false.");
        }

        static void ImportStarterAssets()
        {
            var sample = Sample.FindByPackage(XriPackage, XriVersion).FirstOrDefault(s => s.displayName == "Starter Assets");
            if (string.IsNullOrEmpty(sample.displayName))
            {
                Debug.LogError("[SKYFOLD] XRI Starter Assets sample not found.");
                return;
            }
            if (sample.isImported)
            {
                Debug.Log("[SKYFOLD] Starter Assets already imported at " + sample.importPath);
                return;
            }
            bool ok = sample.Import(Sample.ImportOptions.OverridePreviousImports | Sample.ImportOptions.HideImportWindow);
            Debug.Log("[SKYFOLD] Imported XRI Starter Assets: " + ok + " -> " + sample.importPath);
        }

        static void SetInt(SerializedObject so, string name, int value)
        {
            var p = so.FindProperty(name);
            if (p != null) p.intValue = value; else Debug.LogWarning("[SKYFOLD] URP property missing: " + name);
        }

        static void SetFloat(SerializedObject so, string name, float value)
        {
            var p = so.FindProperty(name);
            if (p != null) p.floatValue = value; else Debug.LogWarning("[SKYFOLD] URP property missing: " + name);
        }

        static void SetBool(SerializedObject so, string name, bool value)
        {
            var p = so.FindProperty(name);
            if (p != null) p.boolValue = value; else Debug.LogWarning("[SKYFOLD] URP property missing: " + name);
        }
    }
}
