using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>Dev tool: renders views of the generated scene to PNG from batch mode (look-dev checks).</summary>
    public static class RenderProbe
    {
        public static void BatchCloudBottom()
        {
            EditorSceneManager.OpenScene("Assets/Skyfold/Scenes/Skyfold.unity");
            var clouds = GameObject.Find("Clouds");
            var cloud = clouds != null && clouds.transform.childCount > 0 ? clouds.transform.GetChild(0) : null;
            string dir = "Logs/renderprobe";
            Directory.CreateDirectory(dir);
            var log = new System.Text.StringBuilder();
            if (cloud == null) { File.WriteAllText(dir + "/log.txt", "no cloud"); EditorApplication.Exit(1); return; }
            var r = cloud.GetComponentInChildren<Renderer>();
            log.AppendLine($"cloud {cloud.name} at {cloud.position} mat {r.sharedMaterial.name} shader {r.sharedMaterial.shader.name}");
            log.AppendLine($"ambientMode {RenderSettings.ambientMode} sky {RenderSettings.ambientSkyColor} eq {RenderSettings.ambientEquatorColor} ground {RenderSettings.ambientGroundColor}");
            var sh = RenderSettings.ambientProbe;
            Vector3[] dirs = { Vector3.up, Vector3.down, Vector3.forward };
            var outCol = new Color[3];
            sh.Evaluate(dirs, outCol);
            log.AppendLine($"ambientProbe up {outCol[0]} down {outCol[1]} fwd {outCol[2]}");

            var camGo = new GameObject("Probe Camera");
            var cam = camGo.AddComponent<Camera>();
            cam.farClipPlane = 3000f;
            cam.fieldOfView = 20f;
            Vector3 target = cloud.position + Vector3.up * 3f;
            Vector3 from = new Vector3(96f, 2f, 40f);
            camGo.transform.position = from;
            camGo.transform.LookAt(target);
            var rt = new RenderTexture(640, 360, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;

            void Shot(string name)
            {
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
                tex.Apply();
                var c = tex.GetPixel(rt.width / 2, rt.height / 2 - 6);
                log.AppendLine($"{name}: centre pixel {c}");
                File.WriteAllBytes($"{dir}/{name}.png", tex.EncodeToPNG());
                RenderTexture.active = null;
            }

            Shot("a_scene");
            var mat = r.sharedMaterial;
            var block = new MaterialPropertyBlock();
            r.GetPropertyBlock(block);
            log.AppendLine($"mpb empty {block.isEmpty}");
            float wrap = mat.GetFloat("_Wrap");
            mat.SetFloat("_Wrap", 1f);
            Shot("b_wrap1");
            mat.SetFloat("_Wrap", wrap);
            var tint = mat.GetColor("_ShadowTint");
            mat.SetColor("_ShadowTint", Color.white);
            Shot("c_tintwhite");
            mat.SetColor("_ShadowTint", tint);
            var amb = RenderSettings.ambientMode;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.5f, 0.5f, 0.5f);
            Shot("d_flat_ambient");
            RenderSettings.ambientMode = amb;
            File.WriteAllText(dir + "/log.txt", log.ToString());
            EditorApplication.Exit(0);
        }
    }
}
