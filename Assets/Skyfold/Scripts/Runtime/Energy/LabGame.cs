using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// The display stand at the back of each lab board: a dark screen tilted up towards the player, with a title,
    /// a content area each game fills, a status line and a fact card shown once the puzzle is solved.
    /// </summary>
    public sealed class LabScreen
    {
        public Transform Root, Content;
        public TextMeshPro Title, Body, Status, Fact;
        public Renderer Accent;

        public const float Width = 1.36f, Height = 0.46f;

        public static LabScreen Make(EnergyLab lab, Transform board, string title, Material accent)
        {
            var s = new LabScreen();
            s.Root = LabKit.Node(board, "Screen", new Vector3(0f, 0.25f, 0.46f), Quaternion.Euler(15f, 0f, 0f)).transform;
            LabKit.Box(s.Root, "Panel", Vector3.zero, new Vector3(Width, Height, 0.02f), lab.ink);
            LabKit.Box(s.Root, "Stand", new Vector3(0f, -0.12f, 0.05f), new Vector3(0.5f, 0.2f, 0.03f), lab.metal);
            s.Accent = LabKit.Box(s.Root, "Accent", new Vector3(0f, Height * 0.5f - 0.008f, -0.011f), new Vector3(Width - 0.04f, 0.008f, 0.004f), accent).GetComponent<Renderer>();
            const float z = -0.0125f;
            s.Title = LabKit.Label(s.Root, title, new Vector3(0f, 0.18f, z), Quaternion.identity, 0.62f, UIStyle.Pearl, Width - 0.08f, 0.08f, true);
            s.Content = LabKit.Node(s.Root, "Content", new Vector3(0f, 0f, z)).transform;
            s.Body = LabKit.Label(s.Content, "", new Vector3(-0.32f, -0.01f, 0f), Quaternion.identity, 0.3f, UIStyle.PearlDeep, 0.62f, 0.27f, false, TextAlignmentOptions.TopLeft);
            s.Status = LabKit.Label(s.Root, "", new Vector3(0f, -0.19f, z), Quaternion.identity, 0.4f, UIStyle.Gold, Width - 0.08f, 0.06f, true);
            s.Fact = LabKit.Label(s.Root, "", new Vector3(0f, -0.02f, z), Quaternion.identity, 0.4f, UIStyle.Pearl, Width - 0.14f, 0.27f, false, TextAlignmentOptions.Center);
            s.Fact.gameObject.SetActive(false);
            return s;
        }

        public void ShowFact(string text)
        {
            Content.gameObject.SetActive(false);
            Fact.text = text;
            Fact.gameObject.SetActive(true);
        }

        public void HideFact()
        {
            Fact.gameObject.SetActive(false);
            Content.gameObject.SetActive(true);
        }
    }

    /// <summary>
    /// One mini-game on the lab table. The EnergyLab ticks the active game with scaled time (so pause freezes it).
    /// A game that runs past its budget solves itself step by step, so every visitor finishes inside three minutes.
    /// </summary>
    public abstract class LabGame
    {
        protected EnergyLab Lab;
        public Transform Board { get; private set; }
        public LabScreen Screen { get; protected set; }

        public float Elapsed { get; private set; }
        public bool Done { get; private set; }
        public bool Assisted { get; private set; }
        public bool Assisting { get; private set; }
        public int Score { get; private set; }
        public int Mistakes { get; protected set; }
        public float SinceDone => Done ? Elapsed - m_DoneAt : 0f;
        float m_DoneAt;

        public abstract string Title { get; }
        public abstract string FactText { get; }
        /// <summary>Noor's caption id (vo_lines.json) played once the puzzle is solved.</summary>
        public abstract string FactLine { get; }
        /// <summary>Seconds before the game starts helping; 0 = never.</summary>
        public virtual float Budget => 60f;
        public virtual string Progress => "";
        public abstract string ResultLine { get; }

        public void Create(EnergyLab lab, Transform board)
        {
            Lab = lab;
            Board = board;
            Build();
        }

        protected abstract void Build();
        protected abstract void ResetGame();
        protected virtual void OnTick(float dt) { }
        protected virtual void OnDoneTick(float dt) { }
        /// <summary>Starts solving the puzzle for the player; must end in <see cref="Complete"/>.</summary>
        protected abstract void BeginAssist();
        /// <summary>Lets go of anything held (board change, pause, restart).</summary>
        public virtual void ReleaseAll() { }

        public void ResetState()
        {
            Elapsed = 0f;
            Done = Assisted = Assisting = false;
            Score = 0;
            Mistakes = 0;
            m_DoneAt = 0f;
            if (Screen != null) Screen.HideFact();
            ResetGame();
        }

        public void Tick(float dt)
        {
            Elapsed += dt;
            if (Done) { OnDoneTick(dt); return; }
            OnTick(dt);
            if (!Done && !Assisting && Budget > 0f && Elapsed >= Budget)
            {
                Assisting = true;
                ReleaseAll();
                DialogueDirector.Instance?.Play("lab.assist");
                HUDMessages.Toast("Out of time on this one. Watch how it works.");
                BeginAssist();
            }
        }

        protected void Complete(int score)
        {
            if (Done) return;
            Done = true;
            Assisted = Assisting;
            Score = Mathf.Clamp(score, 0, 1000);
            m_DoneAt = Elapsed;
            if (Screen != null) Screen.ShowFact(FactText);
            Lab.OnGameComplete(this);
        }

        /// <summary>Score for a puzzle solved in t seconds with some mistakes: 1000 down to a floor of 400.</summary>
        protected static int SpeedScore(float seconds, int mistakes, float perSecond, int perMistake)
            => Mathf.Clamp(Mathf.RoundToInt(1000f - seconds * perSecond - mistakes * perMistake), 400, 1000);

        protected const int AssistScore = 250;
    }
}
