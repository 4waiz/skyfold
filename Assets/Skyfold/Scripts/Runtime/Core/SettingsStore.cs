using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Skyfold
{
    public enum MoveMode { Smooth = 0, TeleportOnly = 1 }
    public enum TurnMode { Snap = 0, Smooth = 1 }
    public enum Guidance { FullTutorial = 0, HintsOnly = 1, Off = 2 }
    public enum DriveComfort { InCar = 0, RemoteOverlook = 1 }

    [Serializable]
    public sealed class GameSettings
    {
        public const int CurrentVersion = 2;
        public int version = CurrentVersion;

        // Audio (linear 0..1)
        public float master = 0.9f;
        public float music = 0.6f;
        public float effects = 0.85f;
        public float voice = 1f;
        public float ambience = 0.7f;

        // Comfort (VR)
        public MoveMode moveMode = MoveMode.Smooth;
        public TurnMode turnMode = TurnMode.Snap;
        public int snapAngle = 45;
        public float smoothTurnSpeed = 60f;
        public float moveSpeed = 2.0f;
        public bool vignette = true;
        public float vignetteStrength = 0.6f;
        public bool seated;
        public float heightOffset;           // metres added to the camera offset (calibration)
        public DriveComfort driveComfort = DriveComfort.InCar;
        public bool comfortChosen;           // first-run comfort choice shown

        // Accessibility / UI
        public bool subtitles = true;
        public float subtitleScale = 1f;
        public Guidance guidance = Guidance.FullTutorial;
        public bool reduceFlashing;

        // Desktop
        public float mouseSensitivity = 1f;
        public bool invertY;
        public float fov = 70f;
        public bool fullscreen = true;
        public int resolutionIndex = -1;
        public bool showDiagnostics;
    }

    /// <summary>Loads and saves JSON files in the player's persistent data folder with safe defaults.</summary>
    public static class JsonFile
    {
        public static string Dir => Application.persistentDataPath;

        public static T Load<T>(string fileName, Func<T> defaults, Func<T, bool> validate, out string note) where T : class
        {
            note = null;
            string path = Path.Combine(Dir, fileName);
            try
            {
                if (!File.Exists(path)) { note = "missing (defaults)"; return defaults(); }
                var text = File.ReadAllText(path);
                var value = JsonUtility.FromJson<T>(text);
                if (value == null || !validate(value)) throw new InvalidDataException("invalid content");
                note = "loaded";
                return value;
            }
            catch (Exception e)
            {
                try
                {
                    if (File.Exists(path)) File.Copy(path, path + ".corrupt-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"), true);
                }
                catch { /* best effort */ }
                note = "unreadable, defaults used (" + e.Message + ")";
                return defaults();
            }
        }

        public static bool Save<T>(string fileName, T value)
        {
            string path = Path.Combine(Dir, fileName);
            try
            {
                Directory.CreateDirectory(Dir);
                string tmp = path + ".tmp";
                File.WriteAllText(tmp, JsonUtility.ToJson(value, true));
                if (File.Exists(path)) File.Delete(path);
                File.Move(tmp, path);
                return true;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[SKYFOLD] Could not save " + fileName + ": " + e.Message);
                return false;
            }
        }
    }

    public static class SettingsStore
    {
        public const string FileName = "settings.json";
        public static GameSettings Current { get; private set; } = new GameSettings();
        public static event Action<GameSettings> Changed;

        public static void Load()
        {
            Current = JsonFile.Load(FileName, () => new GameSettings(), Validate, out var note);
            if (Current.version != GameSettings.CurrentVersion) Current.version = GameSettings.CurrentVersion;
            Debug.Log("[SKYFOLD] Settings " + note + " at " + Path.Combine(JsonFile.Dir, FileName));
        }

        static bool Validate(GameSettings s)
        {
            if (s.version <= 0 || s.version > GameSettings.CurrentVersion) return false;
            s.master = Mathf.Clamp01(s.master);
            s.music = Mathf.Clamp01(s.music);
            s.effects = Mathf.Clamp01(s.effects);
            s.voice = Mathf.Clamp01(s.voice);
            s.ambience = Mathf.Clamp01(s.ambience);
            s.snapAngle = s.snapAngle == 30 || s.snapAngle == 45 || s.snapAngle == 60 || s.snapAngle == 90 ? s.snapAngle : 45;
            s.smoothTurnSpeed = Mathf.Clamp(s.smoothTurnSpeed, 30f, 150f);
            s.moveSpeed = Mathf.Clamp(s.moveSpeed, 1f, 3.5f);
            s.vignetteStrength = Mathf.Clamp01(s.vignetteStrength);
            s.heightOffset = Mathf.Clamp(s.heightOffset, -0.6f, 0.8f);
            s.subtitleScale = Mathf.Clamp(s.subtitleScale, 0.75f, 1.6f);
            s.mouseSensitivity = Mathf.Clamp(s.mouseSensitivity, 0.2f, 4f);
            s.fov = Mathf.Clamp(s.fov, 55f, 95f);
            return true;
        }

        public static void Save()
        {
            JsonFile.Save(FileName, Current);
            Changed?.Invoke(Current);
        }

        public static void Notify() => Changed?.Invoke(Current);
    }

    [Serializable]
    public sealed class EpisodeRecord
    {
        public string id;
        public bool completed;
        public string bestMedal = "";
        public float bestTimeLeft = -1f;
        public int bestScore;
    }

    [Serializable]
    public sealed class SavedPlacement
    {
        public string socket;
        public string piece;
        public ModuleType type;
        public int rotation;
    }

    [Serializable]
    public sealed class CampaignProgress
    {
        public const int CurrentVersion = 1;
        public int version = CurrentVersion;
        public int unlockedEpisode = 1;   // highest playable episode
        public List<EpisodeRecord> episodes = new List<EpisodeRecord>();
        public List<SavedPlacement> placements = new List<SavedPlacement>(); // route carried between episodes
        public bool substationPowered;
        public int resumeEpisode;          // set when the player chose "Restart in VR" mid-session

        public EpisodeRecord Record(string id)
        {
            foreach (var e in episodes) if (e.id == id) return e;
            var r = new EpisodeRecord { id = id };
            episodes.Add(r);
            return r;
        }
    }

    /// <summary>Campaign progress. Demo runs never write here (they use demo.json).</summary>
    public static class ProgressStore
    {
        public const string CampaignFile = "campaign.json";
        public const string DemoFile = "demo.json";

        public static CampaignProgress Campaign { get; private set; } = new CampaignProgress();
        public static CampaignProgress Demo { get; private set; } = new CampaignProgress();

        public static void Load()
        {
            Campaign = JsonFile.Load(CampaignFile, () => new CampaignProgress(), Validate, out var n1);
            Demo = JsonFile.Load(DemoFile, () => new CampaignProgress(), Validate, out var n2);
            Debug.Log($"[SKYFOLD] Campaign progress {n1}; demo progress {n2}");
        }

        static bool Validate(CampaignProgress p)
        {
            if (p.version <= 0 || p.version > CampaignProgress.CurrentVersion) return false;
            p.unlockedEpisode = Mathf.Clamp(p.unlockedEpisode, 1, 3);
            p.episodes ??= new List<EpisodeRecord>();
            p.placements ??= new List<SavedPlacement>();
            return true;
        }

        public static void SaveCampaign() => JsonFile.Save(CampaignFile, Campaign);
        public static void SaveDemo() => JsonFile.Save(DemoFile, Demo);

        public static void ResetDemo()
        {
            Demo = new CampaignProgress();
            SaveDemo();
        }
    }
}
