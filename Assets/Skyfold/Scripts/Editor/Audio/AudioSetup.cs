using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>Builds the AudioLibrary asset from Assets/Skyfold/Audio (and audio_index.json levels).</summary>
    public static class AudioSetup
    {
        public const string Root = "Assets/Skyfold/Audio";
        public const string LibraryPath = "Assets/Skyfold/Audio/AudioLibrary.asset";

        [Serializable] sealed class IndexClip { public string id; public string file; public string category; public bool loop; public float suggested_db; public bool spatial; public string caption; }
        [Serializable] sealed class IndexFile { public int version; public List<IndexClip> clips; }

        [MenuItem("SKYFOLD/Setup/Build Audio Library")]
        public static AudioLibrary Build()
        {
            Directory.CreateDirectory(Root);
            var lib = AssetDatabase.LoadAssetAtPath<AudioLibrary>(LibraryPath);
            if (lib == null)
            {
                lib = ScriptableObject.CreateInstance<AudioLibrary>();
                AssetDatabase.CreateAsset(lib, LibraryPath);
            }
            lib.entries.Clear();

            var index = new Dictionary<string, IndexClip>();
            var indexPath = Path.Combine(Root, "audio_index.json");
            if (File.Exists(indexPath))
            {
                try
                {
                    var f = JsonUtility.FromJson<IndexFile>(File.ReadAllText(indexPath));
                    if (f?.clips != null) foreach (var c in f.clips) if (!string.IsNullOrEmpty(c.id)) index[c.id] = c;
                }
                catch (Exception e) { Debug.LogWarning("[SKYFOLD] audio_index.json unreadable: " + e.Message); }
            }

            foreach (var guid in AssetDatabase.FindAssets("t:AudioClip", new[] { Root }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var clip = AssetDatabase.LoadAssetAtPath<AudioClip>(path);
                if (clip == null) continue;
                string id = Path.GetFileNameWithoutExtension(path);
                var cat = path.Contains("/VO/") ? AudioCategory.Voice : path.Contains("/Music/") ? AudioCategory.Music : path.Contains("/Ambience/") ? AudioCategory.Ambience : AudioCategory.Effects;
                index.TryGetValue(id, out var meta);
                bool loop = meta != null ? meta.loop : id.EndsWith("_loop");
                float db = meta != null ? meta.suggested_db : DefaultDb(id, cat);
                if (meta != null && Mathf.Abs(db) > 40f) db = DefaultDb(id, cat);
                lib.entries.Add(new AudioEntry
                {
                    id = id,
                    clip = clip,
                    category = cat,
                    loop = loop,
                    spatial = meta != null ? meta.spatial : cat == AudioCategory.Effects,
                    volumeDb = db,
                    caption = meta?.caption
                });
            }
            EditorUtility.SetDirty(lib);
            AssetDatabase.SaveAssets();
            Debug.Log($"[SKYFOLD] Audio library: {lib.entries.Count} clips");
            return lib;
        }

        static float DefaultDb(string id, AudioCategory c)
        {
            switch (c)
            {
                case AudioCategory.Music: return -4f;
                case AudioCategory.Ambience: return -6f;
                case AudioCategory.Voice: return 0f;
                default: return id.StartsWith("ui_") ? -8f : -3f;
            }
        }
    }
}
