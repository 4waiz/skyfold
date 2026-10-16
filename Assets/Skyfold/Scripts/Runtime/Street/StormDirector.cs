using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// The approaching magnetic storm, driven by the mission timer: the sky and sun shift from warm
    /// late afternoon toward indigo with a coral edge, a cloud bank rolls in, wind and thunder grow.
    /// No camera shake, no forced flashes when "reduce flashing" is on.
    /// </summary>
    public sealed class StormDirector : MonoBehaviour
    {
        public static StormDirector Instance { get; private set; }

        public Light sun;
        public Material sky;
        public Transform stormFront;
        public Vector3 frontStart = new Vector3(520f, 0f, 300f), frontEnd = new Vector3(230f, 0f, 160f);
        public ParticleSystem rain;
        public Light lightning;

        public Color sunCalm = new Color(1f, 0.86f, 0.68f);
        public Color sunStorm = new Color(0.55f, 0.58f, 0.78f);
        public float sunCalmIntensity = 2.2f, sunStormIntensity = 0.9f;
        public Color ambientCalm = new Color(0.62f, 0.71f, 0.8f), ambientStorm = new Color(0.3f, 0.33f, 0.42f);
        public Color fogCalm = new Color(0.93f, 0.85f, 0.74f), fogStorm = new Color(0.36f, 0.38f, 0.48f);

        float m_Progress;
        float m_NextThunder = 8f;
        float m_Flash;
        static readonly int StormId = Shader.PropertyToID("_Storm");

        public float Progress => m_Progress;

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public void SetProgress(float p)
        {
            m_Progress = Mathf.Clamp01(p);
            Apply();
        }

        void Apply()
        {
            float p = Mathf.SmoothStep(0f, 1f, m_Progress);
            if (sun != null)
            {
                sun.color = Color.Lerp(sunCalm, sunStorm, p);
                sun.intensity = Mathf.Lerp(sunCalmIntensity, sunStormIntensity, p) + m_Flash * 2f;
            }
            RenderSettings.ambientLight = Color.Lerp(ambientCalm, ambientStorm, p);
            RenderSettings.fogColor = Color.Lerp(fogCalm, fogStorm, p);
            if (sky != null) sky.SetFloat(StormId, p);
            if (stormFront != null) stormFront.position = Vector3.Lerp(frontStart, frontEnd, p);
            if (rain != null)
            {
                var em = rain.emission;
                em.rateOverTime = p > 0.82f ? Mathf.Lerp(0f, 900f, (p - 0.82f) / 0.18f) : 0f;
                if (p > 0.82f && !rain.isPlaying) rain.Play();
                if (p <= 0.82f && rain.isPlaying) rain.Stop();
            }
            AudioDirector.Instance?.SetStormIntensity(p);
        }

        void Update()
        {
            if (m_Progress > 0.6f && GameRoot.Instance != null && GameRoot.Instance.IsPlaying)
            {
                m_NextThunder -= Time.deltaTime;
                if (m_NextThunder <= 0f)
                {
                    m_NextThunder = Mathf.Lerp(14f, 5f, m_Progress) + Random.Range(0f, 4f);
                    var cam = PlayerRigs.Instance != null ? PlayerRigs.Instance.ActiveCamera : null;
                    Vector3 at = (cam != null ? cam.transform.position : Vector3.zero) + new Vector3(Random.Range(150f, 260f), 60f, Random.Range(60f, 200f));
                    AudioDirector.Instance?.PlayAt("thunder_far", at, 1f, Random.Range(0.85f, 1.05f), 80f);
                    if (!SettingsStore.Current.reduceFlashing) m_Flash = 0.6f;
                }
            }
            if (m_Flash > 0f)
            {
                m_Flash = Mathf.Max(0f, m_Flash - Time.deltaTime * 2.5f);
                if (lightning != null) { lightning.enabled = m_Flash > 0.05f; lightning.intensity = m_Flash * 3f; }
                Apply();
            }
            else if (lightning != null && lightning.enabled) lightning.enabled = false;
        }
    }
}
