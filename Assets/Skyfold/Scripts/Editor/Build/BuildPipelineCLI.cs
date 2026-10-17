using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// One-command reproducible pipeline (menu SKYFOLD/Build/All or batch -executeMethod):
    /// configure project, patch XRI actions, fonts, audio library, materials, scene, validation,
    /// then a Windows x64 player build (release or development).
    /// </summary>
    public static class BuildPipelineCLI
    {
        public const string ReleaseDir = "Builds/Release/SKYFOLD";
        public const string DevDir = "Builds/Development/SKYFOLD";

        [MenuItem("SKYFOLD/Build/Prepare Content (no player)")]
        public static void Prepare()
        {
            ProjectSetup.ConfigureProject();
            XRIInputPatch.Patch();
            FontSetup.Build();
            IconSetup.Apply();
            AudioSetup.Build();
            MaterialLibrary.BuildAll();
            SceneBuilder.Build();
        }

        [MenuItem("SKYFOLD/Build/All (Release)")]
        public static void BuildAllRelease() => Run(false, true);

        [MenuItem("SKYFOLD/Build/Player Only (Release)")]
        public static void BuildPlayerRelease() => Run(false, false);

        [MenuItem("SKYFOLD/Build/All (Development)")]
        public static void BuildAllDev() => Run(true, true);

        public static void BatchAllRelease() => Batch(() => Run(false, true));
        public static void BatchAllDev() => Batch(() => Run(true, true));
        public static void BatchPrepare() => Batch(Prepare);
        public static void BatchPlayerRelease() => Batch(() => Run(false, false));
        public static void BatchPlayerDev() => Batch(() => Run(true, false));

        static void Batch(Action a)
        {
            try { a(); EditorApplication.Exit(0); }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }

        static void Run(bool development, bool prepare)
        {
            if (prepare) Prepare();
            int problems = ProjectValidator.Validate(true);
            if (problems > 0) Debug.LogWarning($"[SKYFOLD] Validation reported {problems} problem(s); see log.");

            // SKYFOLD_BUILD_DIR lets a test build go elsewhere (e.g. Builds/Staging/SKYFOLD) so it never deletes a
            // release folder another process (a capture, a QA run) is still playing from.
            string dir = Environment.GetEnvironmentVariable("SKYFOLD_BUILD_DIR");
            if (string.IsNullOrEmpty(dir)) dir = development ? DevDir : ReleaseDir;
            // Never half-delete a build that is running: Directory.Delete stops at the first locked file and
            // leaves a folder that can no longer start. A running SKYFOLD.exe cannot be opened for writing.
            string exe = Path.Combine(dir, "SKYFOLD.exe");
            if (File.Exists(exe))
            {
                try { using (File.Open(exe, FileMode.Open, FileAccess.ReadWrite, FileShare.None)) { } }
                catch (Exception e) when (e is IOException || e is UnauthorizedAccessException)
                {
                    throw new Exception($"{exe} is running (a QA run or a capture). Close it before rebuilding into {dir}, or set SKYFOLD_BUILD_DIR to build elsewhere.");
                }
            }
            if (Directory.Exists(dir)) Directory.Delete(dir, true);
            Directory.CreateDirectory(dir);
            var options = new BuildPlayerOptions
            {
                scenes = new[] { SceneBuilder.ScenePath },
                locationPathName = Path.Combine(dir, "SKYFOLD.exe"),
                target = BuildTarget.StandaloneWindows64,
                targetGroup = BuildTargetGroup.Standalone,
                options = development ? BuildOptions.Development | BuildOptions.AllowDebugging : BuildOptions.None
            };
            // A staging build may need to run beside another SKYFOLD (a trailer capture, a release QA run), so it
            // drops the single-instance lock for this build only; release builds keep it (XR runtime safety).
            bool staging = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("SKYFOLD_BUILD_DIR"));
            bool singleInstance = PlayerSettings.forceSingleInstance;
            if (staging) PlayerSettings.forceSingleInstance = false;
            BuildReport report;
            try { report = BuildPipeline.BuildPlayer(options); }
            finally { PlayerSettings.forceSingleInstance = singleInstance; }
            var s = report.summary;
            Debug.Log($"[SKYFOLD] Build {(development ? "development" : "release")}: {s.result}, {s.totalSize / (1024 * 1024)} MB, {s.totalTime.TotalSeconds:0}s, errors {s.totalErrors}, warnings {s.totalWarnings} -> {dir}");
            if (s.result != BuildResult.Succeeded) throw new Exception("Player build failed: " + s.result);
            // Release folders stay clean: remove the debug symbol folder Unity adds.
            if (!development)
            {
                string dontShip = Path.Combine(dir, "SKYFOLD_BurstDebugInformation_DoNotShip");
                if (Directory.Exists(dontShip)) Directory.Delete(dontShip, true);
            }
        }
    }
}
