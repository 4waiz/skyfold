using System;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// One objective / tutorial step. The Id is shared by the caption, the voice clip, the
    /// highlight target, the hints and the completion predicate.
    /// </summary>
    public sealed class ObjectiveDef
    {
        public string Id;
        public string Text;                 // objective card (any mode)
        public string TextDesktop;          // optional desktop-specific card
        public string TextVR;               // optional VR-specific card
        public string Voice;                // base VO id; ".vr"/".desktop" variants are resolved at runtime
        public string[] VoiceBefore;        // lines queued before the step's own line
        public bool PausesStorm;            // tutorial step: the storm waits while the player learns
        public bool Checkpoint;             // capture a checkpoint when this step begins
        public bool TutorialOnly;           // skipped entirely when guidance is off and already complete
        public string GuideTarget;          // SceneRegistry name the guide/NURI points at
        public string[] Hints;              // escalating plain-language hints
        public float HintDelay = 22f;       // seconds before the first hint
        public Func<MissionContext, bool> IsComplete;
        public Action<MissionContext> OnBegin;
        public Action<MissionContext> OnComplete;
        public Func<MissionContext, string> Progress; // optional "1/3" style suffix

        public string CardText(PlayMode mode)
        {
            if (mode == PlayMode.VR && !string.IsNullOrEmpty(TextVR)) return TextVR;
            if (mode == PlayMode.Desktop && !string.IsNullOrEmpty(TextDesktop)) return TextDesktop;
            return Text;
        }
    }

    public enum StartLocation { Atelier, StreetDepot, StreetAirfield, Substation }

    public sealed class MissionDefinition
    {
        public string Id;
        public int Episode;                 // 1..3, 0 = demo
        public string Title;
        public string Subtitle;
        public string Briefing;
        public bool IsDemo;
        public float StormSeconds = 300f;
        public StartLocation Start = StartLocation.Atelier;
        public string ReturnKiosk = "kiosk.A";
        public string[] ActiveSockets = Array.Empty<string>();
        public Dictionary<string, Placement> Presets = new Dictionary<string, Placement>();
        public List<PieceDef> Inventory = new List<PieceDef>();
        public string[] InitialFlags = Array.Empty<string>();
        public bool UseCampaignRoute;       // carry the player's own causeway from earlier episodes
        public bool CellInCradleAtStart;
        public bool ConvoyAtTerminal;
        public string[] IntroVoice = Array.Empty<string>();
        public List<ObjectiveDef> Objectives = new List<ObjectiveDef>();
        public Func<MissionResult, string> MedalFor;
        public string MedalRulesText;
        /// <summary>Played on the Clean Energy Lab instead of the miniature city (the lab replaces it on the plinth).</summary>
        public bool UsesEnergyLab;
        /// <summary>No storm: no countdown, no failure; the HUD shows time played instead.</summary>
        public bool NoStorm;
        /// <summary>Header on the objective card; defaults to "EPISODE n" / "DEMO".</summary>
        public string HudLabel;
        /// <summary>Optional score rule; defaults to the storm-time formula.</summary>
        public Func<MissionResult, int> ScoreFor;

        public bool IsCampaign => !IsDemo;
    }

    public sealed class MissionResult
    {
        public string MissionId;
        public bool Success;
        public float StormSeconds;
        public float TimeLeft;
        public float ElapsedPlay;
        public int PlacementAttempts;
        public int Rejected;
        public int HintsShown;
        public int Retries;
        public int RouteLength;
        public bool UsedShortcut;
        public string Medal = "";
        public int Score;
        public List<string> Notes = new List<string>();
    }

    public enum PlayMode { Desktop, VR }
}
