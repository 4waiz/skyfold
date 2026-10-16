using System;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    public enum AudioCategory { Music, Effects, Voice, Ambience, UI }

    [Serializable]
    public sealed class AudioEntry
    {
        public string id;
        public AudioClip clip;
        public AudioCategory category;
        public bool loop;
        public bool spatial;
        public float volumeDb;
        public string caption;
    }

    /// <summary>Maps audio ids to clips. Built by the editor from Assets/Skyfold/Audio and audio_index.json.</summary>
    [CreateAssetMenu(menuName = "SKYFOLD/Audio Library")]
    public sealed class AudioLibrary : ScriptableObject
    {
        public List<AudioEntry> entries = new List<AudioEntry>();

        Dictionary<string, AudioEntry> m_Map;

        public AudioEntry Get(string id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            if (m_Map == null)
            {
                m_Map = new Dictionary<string, AudioEntry>();
                foreach (var e in entries) if (e != null && !string.IsNullOrEmpty(e.id)) m_Map[e.id] = e;
            }
            return m_Map.TryGetValue(id, out var v) ? v : null;
        }

        public bool Has(string id) => Get(id)?.clip != null;

        /// <summary>Returns a random variant "id_01".."id_0N" if present, else the id itself.</summary>
        public AudioEntry GetVariant(string baseId)
        {
            var direct = Get(baseId);
            if (direct != null && direct.clip != null) return direct;
            var options = new List<AudioEntry>();
            for (int i = 1; i <= 9; i++)
            {
                var e = Get($"{baseId}_{i:00}");
                if (e != null && e.clip != null) options.Add(e);
            }
            return options.Count > 0 ? options[UnityEngine.Random.Range(0, options.Count)] : null;
        }
    }
}
