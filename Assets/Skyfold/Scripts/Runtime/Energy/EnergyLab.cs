using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// The Clean Energy Lab: three sustainability mini-games played on the Atelier plinth, where the miniature city
    /// used to sit. Everything is in arm's reach of one standing spot, so in VR the whole challenge is played without
    /// moving: grip to grab blocks, trigger to use things. The lab builds its boards at runtime from primitives and
    /// the shared palette materials the scene builder assigns, and the mission objectives read its state.
    /// </summary>
    public sealed class EnergyLab : MonoBehaviour
    {
        public static EnergyLab Instance { get; private set; }

        [Header("Palette (SKY_* materials, assigned by the scene builder)")]
        public Material pearl;
        public Material ink, teal, tealGlow, coral, gold, metal, sand, sea, lamp, wood;
        public Material solar, nuclear, battery, gas, mud, leaf, blue;

        [Header("Scene")]
        [Tooltip("Hidden while the lab is out (the miniature city, its tray and route line).")]
        public GameObject[] hideInLab;
        public MiniatureMirror mirror;
        [Tooltip("Where the player stands for the challenge: close enough to reach the blocks.")]
        public Transform playerSpot;

        public EnergyMixGame Mix { get; private set; }
        public CarbonCaptureGame Capture { get; private set; }
        public MangroveGame Mangroves { get; private set; }
        public LabGame[] Games { get; private set; }
        public LabGame Active { get; private set; }
        public bool LabMode { get; private set; }
        public bool FinaleShown => m_Shown == m_Finale && m_Finale != null;

        public const int MaxScore = 3000;
        public int TotalScore
        {
            get
            {
                int t = 0;
                if (Games != null) foreach (var g in Games) t += g.Done ? g.Score : 0;
                return t;
            }
        }

        Transform m_Content, m_Welcome, m_Finale, m_Shown;
        readonly List<Transform> m_Boards = new List<Transform>();
        LabScreen m_FinaleScreen;
        readonly Transform[] m_FinaleBars = new Transform[3];
        readonly TextMeshPro[] m_FinaleValues = new TextMeshPro[3];
        Transform m_Orb;
        float m_ShowT = 1f;
        bool m_Built;

        void Awake()
        {
            Instance = this;
            Build();
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        // ------------------------------------------------------------------ build
        void Build()
        {
            if (m_Built) return;
            m_Built = true;
            m_Content = LabKit.Node(transform, "Lab Content", Vector3.zero).transform;
            // The lab table top over the plinth (the root sits 3 cm up, where the miniature's ground was; the slab
            // reaches down to the plinth), with a glowing front edge. Surfaces on it sit at least 2 mm apart so nothing
            // z-fights in the headset.
            LabKit.Box(m_Content, "Table", new Vector3(0f, -0.011f, 0f), new Vector3(1.48f, 0.038f, 1.02f), pearl);
            LabKit.Box(m_Content, "Front Edge", new Vector3(0f, 0.009f, -0.505f), new Vector3(1.48f, 0.006f, 0.012f), tealGlow);

            m_Welcome = Board("Welcome");
            BuildWelcome();
            Mix = new EnergyMixGame();
            Capture = new CarbonCaptureGame();
            Mangroves = new MangroveGame();
            Games = new LabGame[] { Mix, Capture, Mangroves };
            Mix.Create(this, Board("Energy Mix"));
            Capture.Create(this, Board("Carbon Capture"));
            Mangroves.Create(this, Board("Mangroves"));
            m_Finale = Board("Finale");
            BuildFinale();

            SceneRegistry.Register("lab", transform);
            ShowBoard(m_Welcome, false);
        }

        Transform Board(string name)
        {
            var b = LabKit.Node(m_Content, "Board " + name, Vector3.zero).transform;
            m_Boards.Add(b);
            return b;
        }

        void BuildWelcome()
        {
            var s = LabScreen.Make(this, m_Welcome, "CLEAN ENERGY CHALLENGE", gold);
            s.Body.rectTransform.sizeDelta = new Vector2(1.24f, 0.27f);
            s.Body.transform.localPosition = new Vector3(0f, -0.01f, 0f);
            s.Body.alignment = TextAlignmentOptions.Top;
            s.Body.fontSize = 0.36f;
            s.Body.text =
                "Take this island to <b>net zero</b> in three quick puzzles:\n" +
                "<color=#F5C242>1  Power the city 24/7</color>   ·   <color=#35E0D0>2  Capture the carbon</color>   ·   <color=#6FE09A>3  Plant blue carbon</color>\n\n" +
                "<size=85%>About 3 minutes. Play standing at this table.</size>";
            s.Status.text = "A project by " + SkyfoldInfo.Credit;

            // Three previews of what is coming.
            var a = LabKit.Node(m_Welcome, "Preview Solar", new Vector3(-0.4f, 0.008f, -0.12f)).transform;
            LabKit.Box(a, "Block", new Vector3(0f, 0.025f, 0f), new Vector3(0.11f, 0.05f, 0.11f), solar);
            LabKit.Prim(PrimitiveType.Cube, a, "Panel", new Vector3(0f, 0.056f, 0.022f), new Vector3(0.085f, 0.004f, 0.045f), blue, false, Quaternion.Euler(-20f, 0f, 0f));
            var b = LabKit.Node(m_Welcome, "Preview Pipe", new Vector3(0f, 0.008f, -0.12f)).transform;
            LabKit.Box(b, "Plate", new Vector3(0f, 0.004f, 0f), new Vector3(0.132f, 0.008f, 0.132f), ink);
            LabKit.Rod(b, "Arm", new Vector3(0f, 0.022f, 0.033f), 0.032f, 0.066f, tealGlow, 90f);
            LabKit.Rod(b, "Arm 2", new Vector3(0.033f, 0.022f, 0f), 0.032f, 0.066f, tealGlow, 0f);
            LabKit.Sphere(b, "Hub", new Vector3(0f, 0.022f, 0f), 0.042f, tealGlow);
            var c = LabKit.Node(m_Welcome, "Preview Mangrove", new Vector3(0.4f, 0.008f, -0.12f)).transform;
            LabKit.Cylinder(c, "Mud", new Vector3(0f, 0.004f, 0f), 0.13f, 0.008f, mud);
            LabKit.Cylinder(c, "Trunk", new Vector3(0f, 0.045f, 0f), 0.016f, 0.08f, wood);
            LabKit.Sphere(c, "Canopy", new Vector3(0f, 0.1f, 0f), 0.09f, leaf);
            string[] names = { "POWER", "CARBON", "MANGROVES" };
            for (int i = 0; i < 3; i++)
                LabKit.Label(m_Welcome, names[i], new Vector3(-0.4f + i * 0.4f, 0.0125f, -0.25f), LabKit.Flat, 0.28f, UIStyle.Teal, 0.3f, 0.05f, true);
        }

        void BuildFinale()
        {
            m_FinaleScreen = LabScreen.Make(this, m_Finale, "NET ZERO ISLAND", gold);
            m_FinaleScreen.Body.rectTransform.sizeDelta = new Vector2(1.24f, 0.27f);
            m_FinaleScreen.Body.transform.localPosition = new Vector3(0f, -0.01f, 0f);
            m_FinaleScreen.Body.alignment = TextAlignmentOptions.Top;
            m_FinaleScreen.Body.fontSize = 0.34f;

            // Three score columns rising from the table, one per puzzle, and a glowing orb for the island's power.
            Material[] mats = { solar, tealGlow, leaf };
            string[] names = { "POWER", "CARBON", "MANGROVES" };
            for (int i = 0; i < 3; i++)
            {
                float x = -0.36f + i * 0.36f;
                LabKit.Cylinder(m_Finale, "Base " + i, new Vector3(x, 0.006f, -0.1f), 0.14f, 0.012f, metal);
                var pivot = LabKit.Node(m_Finale, "Column " + i, new Vector3(x, 0.012f, -0.1f)).transform;
                LabKit.Cylinder(pivot, "Bar", new Vector3(0f, 0.5f, 0f), 0.09f, 1f, mats[i]);
                pivot.localScale = new Vector3(1f, 0.0001f, 1f);
                m_FinaleBars[i] = pivot;
                LabKit.Label(m_Finale, names[i], new Vector3(x, 0.0125f, -0.215f), LabKit.Flat, 0.26f, UIStyle.Teal, 0.3f, 0.04f, true);
                m_FinaleValues[i] = LabKit.Label(m_Finale, "", new Vector3(x, 0.0125f, -0.26f), LabKit.Flat, 0.3f, UIStyle.Ink, 0.3f, 0.04f, true);
            }
            m_Orb = LabKit.Sphere(m_Finale, "Island Orb", new Vector3(0f, 0.32f, 0.2f), 0.09f, gold).transform;
        }

        // ------------------------------------------------------------------ flow (called by the mission)
        /// <summary>Puts the lab on the plinth (true) or brings the miniature city back (false).</summary>
        public void SetLabMode(bool on)
        {
            LabMode = on;
            if (hideInLab != null) foreach (var go in hideInLab) if (go != null) go.SetActive(!on);
            if (mirror != null) mirror.hidden = on;
            m_Content.gameObject.SetActive(on);
            var tt = TabletopController.Instance;
            if (on && tt != null)
            {
                tt.ForceDrop();
                foreach (var p in tt.pieces) if (p != null) p.gameObject.SetActive(false);
            }
            if (!on) StopGames();
        }

        /// <summary>Title screen: the welcome board, nothing running.</summary>
        public void ShowAttract()
        {
            SetLabMode(true);
            StopGames();
            foreach (var g in Games) g.ResetState();
            ShowBoard(m_Welcome, false);
        }

        /// <summary>Mission start: every puzzle fresh, the welcome board up until the first objective starts one.</summary>
        public void ResetAll()
        {
            StopGames();
            foreach (var g in Games) g.ResetState();
            ShowBoard(m_Welcome, false);
        }

        public void StartGame(int index)
        {
            if (Games == null || index < 0 || index >= Games.Length) return;
            Active?.ReleaseAll();
            Active = Games[index];
            Active.ResetState();
            ShowBoard(Active.Board, true);
            SceneRegistry.Register("lab.board", Active.Screen.Root);
        }

        public void ShowFinale()
        {
            Active?.ReleaseAll();
            Active = null;
            int total = TotalScore;
            var (rank, _) = Rank(total);
            m_FinaleScreen.Body.text =
                $"<color=#F5C242>{Mix.ResultLine}</color>\n<color=#35E0D0>{Capture.ResultLine}</color>\n<color=#6FE09A>{Mangroves.ResultLine}</color>\n\n" +
                $"<size=120%><b>{total}</b> / {MaxScore}  ·  {rank}</size>";
            m_FinaleScreen.Status.text = "ADNOC is working towards net zero in its operations by 2045";
            for (int i = 0; i < 3; i++) m_FinaleValues[i].text = Games[i].Score.ToString();
            ShowBoard(m_Finale, true);
            m_FinaleT = 0f;
            AudioDirector.Instance?.PlayStinger("stinger_success", 0.8f);
            NuriCompanion.Instance?.Celebrate();
        }

        float m_FinaleT;

        public void StopGames()
        {
            if (Active != null) Active.ReleaseAll();
            Active = null;
            HUDMessages.SetHint(null);
        }

        /// <summary>Moves the player to the challenge spot, facing the table.</summary>
        public void PlacePlayer()
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null || playerSpot == null) return;
            rigs.TeleportTo(playerSpot.position, playerSpot.eulerAngles.y);
        }

        public void OnGameComplete(LabGame game)
        {
            HUDMessages.SetHint(null);
            AudioDirector.Instance?.PlayUI("route_complete", 0.9f);
            NuriCompanion.Instance?.Celebrate();
            DialogueDirector.Instance?.Play(game.FactLine);
            PlayerRigs.Instance?.HapticBoth(0.5f, 0.15f);
            Debug.Log($"[SKYFOLD] Lab game complete: {game.Title} score {game.Score} assisted={game.Assisted} after {game.Elapsed:0.0}s");
        }

        /// <summary>The title a total score earns, and the medal colour it maps to.</summary>
        public static (string title, string medal) Rank(int total)
        {
            if (total >= 2300) return ("Net Zero Hero", "Gold");
            if (total >= 1500) return ("Clean Energy Innovator", "Silver");
            return ("Sustainability Cadet", "Bronze");
        }

        /// <summary>True once game i is solved and its fact has had time to land.</summary>
        public bool GameFinished(int index, float factSeconds = 6.5f)
            => Games != null && index >= 0 && index < Games.Length && Games[index].Done && Games[index].SinceDone >= factSeconds;

        // ------------------------------------------------------------------ per frame
        void ShowBoard(Transform board, bool animate)
        {
            foreach (var b in m_Boards) b.gameObject.SetActive(b == board);
            m_Shown = board;
            m_ShowT = animate ? 0f : 1f;
            if (animate) AudioDirector.Instance?.PlayUI("fold_in", 0.5f);
            if (board != null) board.localPosition = Vector3.zero;
        }

        void Update()
        {
            var root = GameRoot.Instance;
            bool playing = root != null && root.IsPlaying && !root.IsPaused;
            if (Active != null && playing) Active.Tick(Time.deltaTime);

            // A new board rises out of the table.
            if (m_Shown != null && m_ShowT < 1f)
            {
                m_ShowT = Mathf.Min(1f, m_ShowT + Time.unscaledDeltaTime / 0.4f);
                float e = 1f - Mathf.Pow(1f - m_ShowT, 3f);
                m_Shown.localPosition = new Vector3(0f, (e - 1f) * 0.06f, 0f);
            }

            if (m_Shown == m_Finale && m_Finale != null)
            {
                m_FinaleT += Time.unscaledDeltaTime;
                for (int i = 0; i < 3; i++)
                {
                    float target = Mathf.Max(0.02f, Games[i].Score / 1000f) * 0.25f;
                    float grow = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((m_FinaleT - 0.4f - i * 0.35f) / 0.8f));
                    m_FinaleBars[i].localScale = new Vector3(1f, Mathf.Max(0.0001f, target * grow), 1f);
                }
                if (m_Orb != null)
                {
                    float p = 0.09f + 0.012f * Mathf.Sin(m_FinaleT * 3f);
                    m_Orb.localScale = Vector3.one * p;
                    m_Orb.Rotate(0f, 40f * Time.unscaledDeltaTime, 0f, Space.Self);
                }
            }
        }
    }
}
