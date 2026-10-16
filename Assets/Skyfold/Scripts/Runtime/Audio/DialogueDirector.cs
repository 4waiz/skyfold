using System;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    [Serializable]
    public sealed class VoLine
    {
        public string id;
        public string speaker;
        public string mode;
        public string text;
        public string spoken;
    }

    [Serializable]
    sealed class VoFile
    {
        public int version;
        public List<VoLine> lines;
    }

    /// <summary>
    /// Plays Noor's lines one at a time with captions. Lines never overlap; restarting a mission
    /// clears the queue. Missing audio falls back to a timed caption so nothing blocks.
    /// Objective lines carry their objective as context: when the player finishes that objective
    /// before Noor gets to them, they are dropped, so instructions never trail behind the player.
    /// </summary>
    public sealed class DialogueDirector : MonoBehaviour
    {
        public static DialogueDirector Instance { get; private set; }

        public float gapBetweenLines = 0.3f;

        readonly Dictionary<string, VoLine> m_Lines = new Dictionary<string, VoLine>();
        struct Pending
        {
            public string id, context;
            public float queuedAt, maxWait;
        }

        readonly List<Pending> m_Queue = new List<Pending>();
        float m_Clock; // advances only while not paused, so pausing never makes lines stale
        VoLine m_Current;
        float m_Remaining;
        float m_Gap;
        bool m_Paused;

        public event Action<VoLine, float> LineStarted;
        public event Action<VoLine> LineEnded;

        public bool IsSpeaking => m_Current != null || m_Queue.Count > 0;
        public VoLine Current => m_Current;
        public int LoadedLines => m_Lines.Count;
        public PlayMode Mode = PlayMode.Desktop;

        void Awake()
        {
            Instance = this;
            Load();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Load()
        {
            m_Lines.Clear();
            var ta = Resources.Load<TextAsset>("Dialogue/vo_lines");
            if (ta == null) { Debug.LogWarning("[SKYFOLD] vo_lines.json missing"); return; }
            var file = JsonUtility.FromJson<VoFile>(ta.text);
            if (file?.lines == null) return;
            foreach (var l in file.lines) if (!string.IsNullOrEmpty(l.id)) m_Lines[l.id] = l;
        }

        public string Resolve(string baseId)
        {
            if (string.IsNullOrEmpty(baseId)) return null;
            string suffix = Mode == PlayMode.VR ? ".vr" : ".desktop";
            if (m_Lines.ContainsKey(baseId + suffix)) return baseId + suffix;
            return m_Lines.ContainsKey(baseId) ? baseId : null;
        }

        public VoLine GetLine(string baseId)
        {
            var id = Resolve(baseId);
            return id != null && m_Lines.TryGetValue(id, out var l) ? l : null;
        }

        /// <summary>
        /// Queues a line (resolving desktop/VR variants). Duplicate queued lines are ignored.
        /// A context (objective id) lets <see cref="DropContext"/> discard it; maxWait &gt; 0 drops it
        /// if it has waited that many seconds behind other lines.
        /// </summary>
        public void Play(string baseId, string context = null, float maxWait = 0f)
        {
            var id = Resolve(baseId);
            if (id == null) return;
            if (m_Current != null && m_Current.id == id) return;
            foreach (var q in m_Queue) if (q.id == id) return;
            m_Queue.Add(new Pending { id = id, context = context, queuedAt = m_Clock, maxWait = maxWait });
        }

        /// <summary>True while this line (any desktop/VR variant) is playing or waiting in the queue.</summary>
        public bool IsPending(string baseId)
        {
            var id = Resolve(baseId);
            if (id == null) return false;
            if (m_Current != null && m_Current.id == id) return true;
            foreach (var q in m_Queue) if (q.id == id) return true;
            return false;
        }

        /// <summary>Discards queued lines that belong to a finished objective.</summary>
        public void DropContext(string context)
        {
            if (string.IsNullOrEmpty(context)) return;
            m_Queue.RemoveAll(q => q.context == context);
        }

        /// <summary>Stops the current line and the queue, then plays this one now (used for warnings and failure).</summary>
        public void PlayNow(string baseId)
        {
            Stop();
            Play(baseId);
        }

        public void Stop()
        {
            m_Queue.Clear();
            if (m_Current != null)
            {
                var ended = m_Current;
                m_Current = null;
                AudioDirector.Instance?.StopVoice();
                LineEnded?.Invoke(ended);
            }
            m_Remaining = 0f;
            m_Gap = 0f;
        }

        public void SetPaused(bool paused) => m_Paused = paused;

        void Update()
        {
            if (m_Paused) return;
            float dt = Time.unscaledDeltaTime;
            m_Clock += dt;
            if (m_Current != null)
            {
                m_Remaining -= dt;
                var audio = AudioDirector.Instance;
                bool audioDone = audio == null || !audio.VoicePlaying;
                if (m_Remaining <= 0f && audioDone)
                {
                    var ended = m_Current;
                    m_Current = null;
                    m_Gap = gapBetweenLines;
                    LineEnded?.Invoke(ended);
                }
                return;
            }
            if (m_Gap > 0f) { m_Gap -= dt; return; }
            if (m_Queue.Count == 0) return;

            var next = m_Queue[0];
            m_Queue.RemoveAt(0);
            if (next.maxWait > 0f && m_Clock - next.queuedAt > next.maxWait) return; // stale: the moment has passed
            var id = next.id;
            if (!m_Lines.TryGetValue(id, out var line)) return;
            m_Current = line;
            float duration = 0f;
            var entry = AudioDirector.Instance != null && AudioDirector.Instance.library != null ? AudioDirector.Instance.library.Get(id) : null;
            if (entry != null && entry.clip != null)
                duration = AudioDirector.Instance.PlayVoice(entry.clip, entry.volumeDb);
            if (duration <= 0f)
            {
                // Missing audio fallback: show the caption long enough to read it.
                int words = line.text.Split(' ').Length;
                duration = Mathf.Max(1.6f, words / 2.6f + 0.6f);
            }
            m_Remaining = duration;
            LineStarted?.Invoke(line, duration);
        }
    }
}
