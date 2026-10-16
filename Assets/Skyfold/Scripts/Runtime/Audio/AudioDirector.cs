using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Audio;

namespace Skyfold
{
    /// <summary>
    /// Music state machine with crossfades, ambience beds, pooled 2D/3D one-shots, a dedicated
    /// voice channel and dialogue ducking. Routes through the project's AudioMixer groups when
    /// assigned and applies the player's category volumes.
    /// </summary>
    public sealed class AudioDirector : MonoBehaviour
    {
        public static AudioDirector Instance { get; private set; }

        public AudioLibrary library;
        public AudioMixer mixer;
        public AudioMixerGroup musicGroup, effectsGroup, voiceGroup, ambienceGroup, uiGroup;

        [Header("Ducking while dialogue plays")]
        public float musicDuck = 0.42f;
        public float ambienceDuck = 0.6f;
        public float effectsDuck = 0.85f;

        AudioSource m_MusicA, m_MusicB, m_StormLayer, m_AmbA, m_AmbB, m_AmbStorm, m_Voice, m_Ui;
        bool m_MusicOnA = true, m_AmbOnA = true;
        string m_MusicId, m_AmbId;
        float m_MusicFade = 1f, m_AmbFade = 1f;
        float m_MusicFadeSpeed = 0.5f, m_AmbFadeSpeed = 0.5f;
        float m_MusicBaseA = 1f, m_MusicBaseB = 1f, m_AmbBaseA = 1f, m_AmbBaseB = 1f;
        float m_StormIntensity;
        float m_Duck = 1f;
        readonly List<AudioSource> m_Pool2D = new List<AudioSource>();
        readonly List<AudioSource> m_Pool3D = new List<AudioSource>();
        readonly Dictionary<string, float> m_LastPlayed = new Dictionary<string, float>();
        readonly List<AudioSource> m_Loops = new List<AudioSource>();
        bool m_Paused;

        public bool VoicePlaying => m_Voice != null && m_Voice.isPlaying;
        public AudioSource VoiceSource => m_Voice;

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(gameObject); return; }
            Instance = this;
            m_MusicA = MakeSource("Music A", musicGroup, true, false);
            m_MusicB = MakeSource("Music B", musicGroup, true, false);
            m_StormLayer = MakeSource("Storm Layer", musicGroup, true, false);
            m_AmbA = MakeSource("Ambience A", ambienceGroup, true, false);
            m_AmbB = MakeSource("Ambience B", ambienceGroup, true, false);
            m_AmbStorm = MakeSource("Ambience Storm", ambienceGroup, true, false);
            m_Voice = MakeSource("Voice", voiceGroup, false, false);
            m_Ui = MakeSource("UI", uiGroup != null ? uiGroup : effectsGroup, false, false);
            m_Voice.priority = 0;
            for (int i = 0; i < 12; i++) m_Pool2D.Add(MakeSource("SFX2D " + i, effectsGroup, false, false));
            for (int i = 0; i < 24; i++) m_Pool3D.Add(MakeSource("SFX3D " + i, effectsGroup, false, true));
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        AudioSource MakeSource(string n, AudioMixerGroup group, bool loop, bool spatial)
        {
            var go = new GameObject(n);
            go.transform.SetParent(transform, false);
            var s = go.AddComponent<AudioSource>();
            s.playOnAwake = false;
            s.loop = loop;
            s.outputAudioMixerGroup = group;
            s.spatialBlend = spatial ? 1f : 0f;
            s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.minDistance = 2f;
            s.maxDistance = 120f;
            s.dopplerLevel = 0f;
            return s;
        }

        static float DbToLinear(float db) => Mathf.Pow(10f, db / 20f);

        float CategoryVolume(AudioCategory c)
        {
            var s = SettingsStore.Current;
            float v;
            switch (c)
            {
                case AudioCategory.Music: v = s.music; break;
                case AudioCategory.Voice: v = s.voice; break;
                case AudioCategory.Ambience: v = s.ambience; break;
                default: v = s.effects; break;
            }
            return v * s.master;
        }

        // ------------------------------------------------------------------ music
        public void SetMusic(string id, float fadeSeconds = 2f)
        {
            if (id == m_MusicId) return;
            m_MusicId = id;
            var e = library != null ? library.Get(id) : null;
            var next = m_MusicOnA ? m_MusicB : m_MusicA;
            m_MusicOnA = !m_MusicOnA;
            if (e != null && e.clip != null)
            {
                next.clip = e.clip;
                next.loop = e.loop;
                next.volume = 0f;
                next.Play();
                if (m_MusicOnA) m_MusicBaseA = DbToLinear(e.volumeDb); else m_MusicBaseB = DbToLinear(e.volumeDb);
            }
            else
            {
                next.Stop();
                next.clip = null;
            }
            m_MusicFade = 0f;
            m_MusicFadeSpeed = 1f / Mathf.Max(0.05f, fadeSeconds);
        }

        public void PlayStinger(string id, float volume = 1f) => PlayUI(id, volume);

        public void SetStormIntensity(float t) => m_StormIntensity = Mathf.Clamp01(t);

        // ------------------------------------------------------------------ ambience
        public void SetAmbience(string id, float fadeSeconds = 2.5f)
        {
            if (id == m_AmbId) return;
            m_AmbId = id;
            var e = library != null ? library.Get(id) : null;
            var next = m_AmbOnA ? m_AmbB : m_AmbA;
            m_AmbOnA = !m_AmbOnA;
            if (e != null && e.clip != null)
            {
                next.clip = e.clip;
                next.volume = 0f;
                next.Play();
                if (m_AmbOnA) m_AmbBaseA = DbToLinear(e.volumeDb); else m_AmbBaseB = DbToLinear(e.volumeDb);
            }
            else next.Stop();
            m_AmbFade = 0f;
            m_AmbFadeSpeed = 1f / Mathf.Max(0.05f, fadeSeconds);
        }

        // ------------------------------------------------------------------ one-shots
        bool Throttled(string id, float minGap)
        {
            float now = Time.unscaledTime;
            if (m_LastPlayed.TryGetValue(id, out var t) && now - t < minGap) return true;
            m_LastPlayed[id] = now;
            return false;
        }

        public AudioSource Play2D(string id, float volume = 1f, float pitch = 1f)
        {
            var e = library != null ? library.GetVariant(id) : null;
            if (e == null || e.clip == null || Throttled(id, 0.05f)) return null;
            var src = FreeSource(m_Pool2D);
            src.clip = e.clip;
            src.pitch = pitch;
            src.volume = volume * DbToLinear(e.volumeDb) * CategoryVolume(e.category) * (m_Duck < 1f ? effectsDuck : 1f);
            src.Play();
            return src;
        }

        public void PlayUI(string id, float volume = 1f)
        {
            var e = library != null ? library.GetVariant(id) : null;
            if (e == null || e.clip == null || Throttled(id, 0.04f)) return;
            m_Ui.PlayOneShot(e.clip, volume * DbToLinear(e.volumeDb) * CategoryVolume(AudioCategory.Effects));
        }

        public AudioSource PlayAt(string id, Vector3 position, float volume = 1f, float pitch = 1f, float minDistance = 2f)
        {
            var e = library != null ? library.GetVariant(id) : null;
            if (e == null || e.clip == null || Throttled(id + position.GetHashCode(), 0.05f)) return null;
            var src = FreeSource(m_Pool3D);
            src.transform.position = position;
            src.clip = e.clip;
            src.pitch = pitch;
            src.minDistance = minDistance;
            src.volume = volume * DbToLinear(e.volumeDb) * CategoryVolume(e.category);
            src.Play();
            return src;
        }

        static AudioSource FreeSource(List<AudioSource> pool)
        {
            AudioSource oldest = pool[0];
            foreach (var s in pool)
            {
                if (!s.isPlaying) return s;
                if (s.time > oldest.time) oldest = s;
            }
            oldest.Stop();
            return oldest;
        }

        /// <summary>A looping source owned by a world object (car motor, aircraft engine).</summary>
        public AudioSource CreateLoop(string id, Transform parent, float minDistance = 3f, bool spatial = true)
        {
            var e = library != null ? library.Get(id) : null;
            var go = new GameObject("Loop " + id);
            go.transform.SetParent(parent, false);
            var s = go.AddComponent<AudioSource>();
            s.playOnAwake = false;
            s.loop = true;
            s.spatialBlend = spatial ? 1f : 0f;
            s.minDistance = minDistance;
            s.maxDistance = 200f;
            s.dopplerLevel = 0f;
            s.outputAudioMixerGroup = effectsGroup;
            s.clip = e?.clip;
            s.volume = 0f;
            m_Loops.Add(s);
            return s;
        }

        public float LoopGain(string id)
        {
            var e = library != null ? library.Get(id) : null;
            return (e != null ? DbToLinear(e.volumeDb) : 1f) * CategoryVolume(AudioCategory.Effects) * (m_Duck < 1f ? effectsDuck : 1f);
        }

        // ------------------------------------------------------------------ voice
        public float PlayVoice(AudioClip clip, float volumeDb = 0f)
        {
            m_Voice.Stop();
            if (clip == null) return 0f;
            m_Voice.clip = clip;
            m_Voice.volume = DbToLinear(volumeDb) * CategoryVolume(AudioCategory.Voice);
            m_Voice.Play();
            return clip.length;
        }

        public void StopVoice() => m_Voice.Stop();

        public void SetPaused(bool paused)
        {
            m_Paused = paused;
            AudioListener.pause = false; // menus keep UI sounds; world loops pause individually
            foreach (var s in m_Pool3D) { if (paused) s.Pause(); else s.UnPause(); }
            foreach (var s in m_Loops) { if (s == null) continue; if (paused) s.Pause(); else s.UnPause(); }
            if (paused) m_Voice.Pause(); else m_Voice.UnPause();
        }

        public void StopAllWorld()
        {
            foreach (var s in m_Pool3D) s.Stop();
            foreach (var s in m_Pool2D) s.Stop();
            m_Voice.Stop();
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            float duckTarget = VoicePlaying && !m_Paused ? 0f : 1f; // 0 = ducked
            m_Duck = Mathf.MoveTowards(m_Duck, duckTarget, dt * (duckTarget < m_Duck ? 4f : 1.2f));
            float duckMusic = Mathf.Lerp(musicDuck, 1f, m_Duck);
            float duckAmb = Mathf.Lerp(ambienceDuck, 1f, m_Duck);

            m_MusicFade = Mathf.MoveTowards(m_MusicFade, 1f, dt * m_MusicFadeSpeed);
            m_AmbFade = Mathf.MoveTowards(m_AmbFade, 1f, dt * m_AmbFadeSpeed);
            float music = CategoryVolume(AudioCategory.Music) * duckMusic;
            float amb = CategoryVolume(AudioCategory.Ambience) * duckAmb;
            float pausedMul = m_Paused ? 0.55f : 1f;

            var curMusic = m_MusicOnA ? m_MusicA : m_MusicB;
            var oldMusic = m_MusicOnA ? m_MusicB : m_MusicA;
            float curBase = m_MusicOnA ? m_MusicBaseA : m_MusicBaseB;
            float oldBase = m_MusicOnA ? m_MusicBaseB : m_MusicBaseA;
            curMusic.volume = music * curBase * m_MusicFade * pausedMul * (1f - m_StormIntensity * 0.35f);
            oldMusic.volume = music * oldBase * (1f - m_MusicFade) * pausedMul;
            if (m_MusicFade >= 1f && oldMusic.isPlaying) oldMusic.Stop();

            var curAmb = m_AmbOnA ? m_AmbA : m_AmbB;
            var oldAmb = m_AmbOnA ? m_AmbB : m_AmbA;
            float curAmbBase = m_AmbOnA ? m_AmbBaseA : m_AmbBaseB;
            float oldAmbBase = m_AmbOnA ? m_AmbBaseB : m_AmbBaseA;
            curAmb.volume = amb * curAmbBase * m_AmbFade * pausedMul;
            oldAmb.volume = amb * oldAmbBase * (1f - m_AmbFade) * pausedMul;
            if (m_AmbFade >= 1f && oldAmb.isPlaying) oldAmb.Stop();

            // Storm layers follow the storm intensity.
            UpdateLayer(m_StormLayer, "music_storm_loop", music * 0.8f * Mathf.SmoothStep(0f, 1f, (m_StormIntensity - 0.45f) / 0.55f) * pausedMul);
            UpdateLayer(m_AmbStorm, "amb_storm_loop", amb * Mathf.SmoothStep(0f, 1f, (m_StormIntensity - 0.3f) / 0.7f) * pausedMul);

            if (m_Voice.isPlaying) m_Voice.volume = CategoryVolume(AudioCategory.Voice);
        }

        void UpdateLayer(AudioSource src, string id, float volume)
        {
            if (volume <= 0.001f)
            {
                if (src.isPlaying) src.Stop();
                return;
            }
            if (!src.isPlaying)
            {
                var e = library != null ? library.Get(id) : null;
                if (e == null || e.clip == null) return;
                src.clip = e.clip;
                src.Play();
            }
            src.volume = volume;
        }
    }
}
