using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Mini-game 3, "Blue carbon coast": a timed round on a strip of coast (sand, mudflat, sea). Up to three mudflat
    /// spots glow at a time; use a glowing spot to plant a mangrove there before it fades. Twelve spots, 25 seconds.
    /// </summary>
    public sealed class MangroveGame : LabGame
    {
        const float ReadyTime = 2f;
        public const float RoundTime = 25f;
        const int MaxLit = 3;
        const float LitLife = 3.2f;

        sealed class Spot
        {
            public GameObject Root;
            public Renderer Ring;
            public Transform Marker, Tree;
            public LabButton Button;
            public bool Lit, Planted;
            public float LitAge, Grow;
        }

        readonly List<Spot> m_Spots = new List<Spot>();
        readonly System.Random m_Rng = new System.Random();
        int m_Planted;
        float m_Respawn;

        public int Planted => m_Planted;
        public int SpotCount => m_Spots.Count;
        float RoundElapsed => Mathf.Max(0f, Elapsed - ReadyTime);
        public float TimeLeft => Mathf.Clamp(RoundTime - RoundElapsed, 0f, RoundTime);
        bool Running => !Done && Elapsed >= ReadyTime;

        public override string Title => "Blue carbon coast";
        public override float Budget => 0f; // the round timer ends it
        public override string FactLine => "lab.fact.mangrove";
        public override string FactText =>
            $"<b><color=#6FE09A>{m_Planted} mangroves planted!</color></b>\n\n" +
            "Mangroves lock carbon away in their roots and mud, and shelter fish and birds.\n" +
            "<size=85%>ADNOC aims to plant 10 million mangroves by 2030, using drones that scatter seeds. It passed 5 million in January 2026.</size>";
        public override string Progress => Elapsed < ReadyTime ? "Get ready…" : $"{m_Planted} planted · {Mathf.CeilToInt(TimeLeft)} s";
        public override string ResultLine => $"Blue carbon coast: {m_Planted} of {m_Spots.Count} mangroves planted";

        // ------------------------------------------------------------------ build
        protected override void Build()
        {
            var lab = Lab;
            Screen = LabScreen.Make(lab, Board, "BLUE CARBON COAST", lab.leaf);
            Screen.Body.rectTransform.sizeDelta = new Vector2(0.8f, 0.27f);
            Screen.Body.transform.localPosition = new Vector3(-0.22f, -0.01f, 0f);
            Screen.Body.text =
                "Plant mangroves on the mudflats before each glowing spot fades.\n\n" +
                "<color=#6FE09A>VR:</color> point and pull the <b>trigger</b>.\n" +
                "<color=#6FE09A>Laptop:</color> <b>click</b> a glowing spot.\n" +
                "12 spots, 25 seconds. Go!";

            LabKit.Box(Board, "Sea", new Vector3(0f, 0.006f, 0.18f), new Vector3(1.36f, 0.008f, 0.26f), lab.sea);
            LabKit.Box(Board, "Mudflat", new Vector3(0f, 0.006f, -0.085f), new Vector3(1.36f, 0.012f, 0.27f), lab.mud);
            LabKit.Box(Board, "Beach", new Vector3(0f, 0.006f, -0.335f), new Vector3(1.36f, 0.008f, 0.23f), lab.sand);
            LabKit.Label(Board, "MUDFLAT", new Vector3(-0.56f, 0.014f, 0.025f), LabKit.Flat, 0.24f, UIStyle.Pearl, 0.2f, 0.04f, true);
            LabKit.Label(Board, "SEA", new Vector3(-0.56f, 0.0115f, 0.22f), LabKit.Flat, 0.24f, UIStyle.Pearl, 0.2f, 0.04f, true);

            for (int row = 0; row < 2; row++)
                for (int i = 0; i < 6; i++)
                {
                    float x = row == 0 ? -0.55f + i * 0.22f : -0.495f + i * 0.198f;
                    float z = row == 0 ? -0.16f : -0.03f;
                    m_Spots.Add(MakeSpot(new Vector3(x, 0.012f, z), m_Spots.Count));
                }
        }

        Spot MakeSpot(Vector3 pos, int index)
        {
            var lab = Lab;
            var s = new Spot();
            s.Root = LabKit.Node(Board, "Spot " + index, pos);
            var col = s.Root.AddComponent<BoxCollider>();
            col.center = new Vector3(0f, 0.03f, 0f);
            col.size = new Vector3(0.12f, 0.07f, 0.11f);
            LabKit.Cylinder(s.Root.transform, "Hole", new Vector3(0f, 0.0015f, 0f), 0.07f, 0.003f, lab.ink);
            s.Ring = LabKit.Cylinder(s.Root.transform, "Ring", new Vector3(0f, 0f, 0f), 0.1f, 0.002f, lab.tealGlow).GetComponent<Renderer>();
            s.Marker = LabKit.Sphere(s.Root.transform, "Marker", new Vector3(0f, 0.07f, 0f), 0.025f, lab.gold).transform;

            s.Tree = LabKit.Node(s.Root.transform, "Mangrove", Vector3.zero).transform;
            LabKit.Cylinder(s.Tree, "Trunk", new Vector3(0f, 0.035f, 0f), 0.012f, 0.07f, lab.wood);
            for (int r = 0; r < 3; r++)
            {
                float a = r * 120f;
                // Prop roots: the stilts mangroves stand on.
                LabKit.Prim(PrimitiveType.Cylinder, s.Tree, "Root " + r, Quaternion.Euler(0f, a, 0f) * new Vector3(0.012f, 0.012f, 0f),
                    new Vector3(0.006f, 0.016f, 0.006f), lab.wood, false, Quaternion.Euler(0f, a, 35f));
            }
            LabKit.Sphere(s.Tree, "Canopy", new Vector3(0f, 0.08f, 0f), 0.075f, lab.leaf);
            LabKit.Sphere(s.Tree, "Canopy 2", new Vector3(0.022f, 0.068f, 0.012f), 0.05f, lab.leaf);

            s.Button = LabButton.Make(s.Root, "Plant a mangrove");
            var spot = s;
            s.Button.Usable = () => Running && spot.Lit && !spot.Planted;
            s.Button.Blocked = () => spot.Planted ? "Already planted." : Running ? "Wait for it to glow: that's the best mud for a seedling." : null;
            s.Button.Pressed = who => Plant(spot);
            return s;
        }

        // ------------------------------------------------------------------ play
        protected override void ResetGame()
        {
            m_Planted = 0;
            m_Respawn = 0f;
            foreach (var s in m_Spots)
            {
                s.Lit = s.Planted = false;
                s.LitAge = 0f;
                s.Grow = 0f;
                s.Tree.localScale = Vector3.one * 0.0001f;
                s.Tree.gameObject.SetActive(false);
                s.Ring.enabled = false;
                s.Marker.gameObject.SetActive(false);
            }
            Screen.Status.text = "Get ready…";
        }

        void Plant(Spot s)
        {
            if (!Running || !s.Lit || s.Planted) return;
            s.Lit = false;
            s.Planted = true;
            s.Grow = 0f;
            s.Tree.gameObject.SetActive(true);
            m_Planted++;
            AudioDirector.Instance?.PlayAt("socket_snap", s.Root.transform.position, 0.9f, 1.15f);
            if (m_Planted % 4 == 0) NuriCompanion.Instance?.React(NuriMood.Happy, s.Root.transform);
            if (m_Planted >= m_Spots.Count) Finish();
        }

        void Finish()
        {
            foreach (var s in m_Spots) s.Lit = false;
            int bonus = m_Planted >= m_Spots.Count ? Mathf.RoundToInt(TimeLeft * 15f) : 0;
            Screen.Status.text = $"<color=#6FE09A>{m_Planted} MANGROVES PLANTED</color>";
            Complete(m_Planted * 70 + bonus);
        }

        protected override void OnTick(float dt)
        {
            if (Elapsed < ReadyTime)
            {
                Screen.Status.text = "Get ready… " + Mathf.CeilToInt(ReadyTime - Elapsed);
                Animate(dt);
                return;
            }
            if (TimeLeft <= 0f) { Finish(); Animate(dt); return; }

            int lit = 0;
            foreach (var s in m_Spots)
            {
                if (!s.Lit) continue;
                s.LitAge += dt;
                if (s.LitAge > LitLife) { s.Lit = false; m_Respawn = Mathf.Min(m_Respawn, 0.15f); }
                else lit++;
            }
            m_Respawn -= dt;
            if (lit < MaxLit && m_Respawn <= 0f && LightOne()) m_Respawn = 0.35f;
            Screen.Status.text = $"Planted <b>{m_Planted}</b>   ·   <b>{Mathf.CeilToInt(TimeLeft)}</b> s left";
            Animate(dt);
        }

        protected override void OnDoneTick(float dt) => Animate(dt);

        bool LightOne()
        {
            var free = new List<Spot>();
            foreach (var s in m_Spots) if (!s.Lit && !s.Planted) free.Add(s);
            if (free.Count == 0) return false;
            var pick = free[m_Rng.Next(free.Count)];
            pick.Lit = true;
            pick.LitAge = 0f;
            AudioDirector.Instance?.PlayAt("hint_ping", pick.Root.transform.position, 0.35f, 1.3f);
            return true;
        }

        void Animate(float dt)
        {
            float t = Time.time;
            foreach (var s in m_Spots)
            {
                if (s.Ring.enabled != s.Lit) s.Ring.enabled = s.Lit;
                if (s.Marker.gameObject.activeSelf != s.Lit) s.Marker.gameObject.SetActive(s.Lit);
                if (s.Lit)
                {
                    // Fades as its time runs out.
                    float life = 1f - s.LitAge / LitLife;
                    LabKit.Tint(s.Ring, UIStyle.TealGlow, 1.2f + 1.6f * life * (0.75f + 0.25f * Mathf.Sin(t * 9f)));
                    s.Marker.localPosition = new Vector3(0f, 0.065f + Mathf.Sin(t * 5f + s.Root.transform.position.x * 10f) * 0.01f, 0f);
                }
                if (s.Planted && s.Grow < 1f)
                {
                    s.Grow = Mathf.Min(1f, s.Grow + dt / 0.45f);
                    float e = 1f - Mathf.Pow(1f - s.Grow, 3f);
                    s.Tree.localScale = Vector3.one * Mathf.Max(0.0001f, e * (1f + 0.15f * Mathf.Sin(e * Mathf.PI)));
                }
            }
        }

        protected override void BeginAssist() => Finish();

        /// <summary>QA: plants whatever is glowing, as a quick player would.</summary>
        public void QAPlantLit()
        {
            foreach (var s in m_Spots)
                if (s.Lit && !s.Planted) s.Button.Interact(InteractorKind.Desktop);
        }
    }
}
