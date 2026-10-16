using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Short controlled fades for scale changes, teleports and respawns. A small inside-out sphere is
    /// attached to every registered camera (desktop and XR) so the fade works in both eyes.
    /// </summary>
    public sealed class ScreenFader : MonoBehaviour
    {
        public static ScreenFader Instance { get; private set; }
        public Shader fadeShader;
        public Color color = new Color(0.04f, 0.07f, 0.09f, 1f);

        Material m_Material;
        float m_Alpha;
        readonly List<GameObject> m_Spheres = new List<GameObject>();
        static readonly int ColorId = Shader.PropertyToID("_Color");

        public float Alpha => m_Alpha;
        public bool IsFading { get; private set; }

        void Awake()
        {
            Instance = this;
            if (fadeShader == null) fadeShader = Shader.Find("Skyfold/Fade");
            m_Material = new Material(fadeShader) { name = "Fade (runtime)" };
            Apply();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        public void AttachTo(Camera cam)
        {
            if (cam == null || cam.transform.Find("ScreenFade") != null) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = "ScreenFade";
            var col = go.GetComponent<Collider>();
            if (col != null) Destroy(col);
            go.transform.SetParent(cam.transform, false);
            go.transform.localPosition = Vector3.zero;
            go.transform.localScale = Vector3.one * 0.35f;
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = m_Material;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            m_Spheres.Add(go);
            Apply();
        }

        void Apply()
        {
            var c = color;
            c.a = m_Alpha;
            if (m_Material != null) m_Material.SetColor(ColorId, c);
            bool visible = m_Alpha > 0.001f;
            for (int i = m_Spheres.Count - 1; i >= 0; i--)
            {
                if (m_Spheres[i] == null) { m_Spheres.RemoveAt(i); continue; }
                if (m_Spheres[i].activeSelf != visible) m_Spheres[i].SetActive(visible);
            }
        }

        public void SetAlpha(float a)
        {
            m_Alpha = Mathf.Clamp01(a);
            Apply();
        }

        public IEnumerator FadeTo(float target, float seconds)
        {
            IsFading = true;
            float start = m_Alpha;
            float t = 0f;
            seconds = Mathf.Max(0.01f, seconds);
            while (t < seconds)
            {
                t += Time.unscaledDeltaTime;
                SetAlpha(Mathf.Lerp(start, target, Mathf.SmoothStep(0f, 1f, t / seconds)));
                yield return null;
            }
            SetAlpha(target);
            IsFading = false;
        }

        public IEnumerator FadeOut(float seconds = 0.25f) => FadeTo(1f, seconds);
        public IEnumerator FadeIn(float seconds = 0.3f) => FadeTo(0f, seconds);
    }
}
