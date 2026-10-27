using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Mini-game 2, "Capture the carbon": a 4 x 3 grid of pipe tiles between a CO2 capture unit (west) and a storage
    /// well (east). Point at a tile and use it to turn it a quarter. Pipes connected to the source glow; the puzzle is
    /// solved when the flow reaches the well. The path tiles start scrambled; the decoys are random.
    /// </summary>
    public sealed class CarbonCaptureGame : LabGame
    {
        const int Cols = 4, Rows = 3;
        const float Pitch = 0.145f, TileSize = 0.132f;
        const int N = 1, E = 2, S = 4, W = 8;
        static readonly Vector3 GridCentre = new Vector3(0f, 0.012f, -0.13f);

        sealed class Tile
        {
            public int X, Y;
            public bool Corner;
            public int Rotation, Solution = -1;
            public Transform Spin;
            public GameObject Root;
            public LabButton Button;
            public readonly List<Renderer> Pipes = new List<Renderer>();
            public float SpinFrom, SpinTo, SpinT = 1f;
            public bool Lit;
            public int Openings => Rotate(Corner ? (N | E) : (N | S), Rotation);
            public bool OnPath => Solution >= 0;
        }

        // The route the scramble hides: (x, y, corner, solution rotation). y = 0 is the row nearest the player.
        static readonly (int x, int y, bool corner, int rot)[] Path =
        {
            (0, 1, false, 1), // west-east
            (1, 1, true, 3),  // west-north
            (1, 2, true, 1),  // south-east
            (2, 2, false, 1), // west-east
            (3, 2, true, 2),  // west-south
            (3, 1, true, 0),  // north-east, out to the well
        };
        static readonly (int x, int y, bool corner)[] Decoys =
        {
            (0, 0, true), (1, 0, false), (2, 0, true), (3, 0, false), (0, 2, true), (2, 1, true)
        };

        readonly Tile[,] m_Tiles = new Tile[Cols, Rows];
        readonly List<Tile> m_All = new List<Tile>();
        Renderer m_SourceGlow, m_WellGlow;
        Transform m_Smoke;
        int m_Turns, m_Reached;
        float m_AssistStep;
        System.Random m_Rng = new System.Random();

        public override string Title => "Capture the carbon";
        public override float Budget => 55f;
        public override string FactLine => "lab.fact.ccs";
        public override string FactText =>
            "<b><color=#35E0D0>" + LabKit.CO2 + " locked away underground!</color></b>\n\n" +
            "Carbon capture traps " + LabKit.CO2 + " before it reaches the air and stores it deep in rock.\n" +
            "<size=85%>ADNOC's Al Reyadah plant can capture 800,000 tonnes of " + LabKit.CO2 + " a year. The goal: 10 million tonnes a year by 2030.</size>";
        public override string Progress => $"{m_Reached}/{Path.Length} pipes flowing";
        public override string ResultLine => Assisted ? "Capture the carbon: solved with help" : $"Capture the carbon: solved with {m_Turns} turns";

        static int Rotate(int mask, int quarters)
        {
            quarters &= 3;
            for (int i = 0; i < quarters; i++) mask = ((mask << 1) | (mask >> 3)) & 15;
            return mask;
        }

        Vector3 TilePos(int x, int y) => GridCentre + new Vector3((x - (Cols - 1) * 0.5f) * Pitch, 0f, (y - (Rows - 1) * 0.5f) * Pitch);

        // ------------------------------------------------------------------ build
        protected override void Build()
        {
            var lab = Lab;
            Screen = LabScreen.Make(lab, Board, "CAPTURE THE CARBON", lab.tealGlow);
            Screen.Body.rectTransform.sizeDelta = new Vector2(1.24f, 0.27f);
            Screen.Body.transform.localPosition = new Vector3(0f, -0.01f, 0f);
            Screen.Body.text =
                "The plant on the left is releasing " + LabKit.CO2 + ". Turn the pipes to carry it to the <b>storage well</b> on the right, deep underground.\n\n" +
                "<color=#35E0D0>VR:</color> point at a pipe and pull the <b>trigger</b> to turn it.\n" +
                "<color=#35E0D0>Laptop:</color> <b>click</b> a pipe to turn it.\n" +
                "Glowing pipes are connected.";

            // Base plate under the grid.
            LabKit.Box(Board, "Grid Plate", GridCentre + new Vector3(0f, -0.003f, 0f), new Vector3(Cols * Pitch + 0.02f, 0.006f, Rows * Pitch + 0.02f), lab.ink);

            foreach (var p in Path) MakeTile(p.x, p.y, p.corner).Solution = p.rot;
            foreach (var d in Decoys) MakeTile(d.x, d.y, d.corner);

            // The capture unit (west) and the storage well (east), level with the middle row.
            Vector3 west = TilePos(0, 1) + new Vector3(-0.17f, 0f, 0f);
            var plant = LabKit.Node(Board, "Capture Unit", west).transform;
            LabKit.Box(plant, "Body", new Vector3(0f, 0.045f, 0f), new Vector3(0.12f, 0.09f, 0.12f), lab.pearl);
            LabKit.Cylinder(plant, "Stack", new Vector3(-0.025f, 0.13f, 0.02f), 0.035f, 0.08f, lab.metal);
            m_SourceGlow = LabKit.Box(plant, "Valve", new Vector3(0.062f, 0.03f, 0f), new Vector3(0.008f, 0.03f, 0.05f), lab.coral).GetComponent<Renderer>();
            LabKit.Rod(plant, "Outlet", new Vector3(0.07f, 0.03f, 0f), 0.03f, 0.05f, lab.metal);
            m_Smoke = LabKit.Sphere(plant, "CO2 Cloud", new Vector3(-0.025f, 0.2f, 0.02f), 0.06f, lab.gas).transform;
            LabKit.Label(plant, "CAPTURE\nUNIT", new Vector3(0f, 0.092f, -0.02f), LabKit.Flat, 0.2f, UIStyle.Ink, 0.12f, 0.06f, true);

            Vector3 east = TilePos(Cols - 1, 1) + new Vector3(0.17f, 0f, 0f);
            var well = LabKit.Node(Board, "Storage Well", east).transform;
            LabKit.Cylinder(well, "Head", new Vector3(0f, 0.03f, 0f), 0.11f, 0.06f, lab.metal);
            m_WellGlow = LabKit.Cylinder(well, "Cap", new Vector3(0f, 0.062f, 0f), 0.08f, 0.006f, lab.ink).GetComponent<Renderer>();
            LabKit.Rod(well, "Inlet", new Vector3(-0.07f, 0.03f, 0f), 0.03f, 0.05f, lab.metal);
            LabKit.Label(Board, "STORAGE\nWELL", east + new Vector3(0f, 0.004f, -0.1f), LabKit.Flat, 0.2f, UIStyle.Ink, 0.14f, 0.06f, true);
            LabKit.Label(Board, LabKit.CO2 + " SOURCE", west + new Vector3(0f, 0.004f, -0.1f), LabKit.Flat, 0.2f, UIStyle.Coral, 0.16f, 0.04f, true);
        }

        Tile MakeTile(int x, int y, bool corner)
        {
            var lab = Lab;
            var t = new Tile { X = x, Y = y, Corner = corner };
            t.Root = LabKit.Node(Board, $"Pipe {x},{y}", TilePos(x, y));
            var plate = LabKit.Box(t.Root.transform, "Plate", new Vector3(0f, 0.004f, 0f), new Vector3(TileSize, 0.008f, TileSize), lab.pearl);
            var col = plate.AddComponent<BoxCollider>();
            col.center = new Vector3(0f, 2f, 0f);
            col.size = new Vector3(1f, 6f, 1f);
            t.Spin = LabKit.Node(t.Root.transform, "Spin", new Vector3(0f, 0.022f, 0f)).transform;
            // Arms from the centre to each opening at rotation 0, then a hub.
            float half = TileSize * 0.5f;
            int baseMask = corner ? (N | E) : (N | S);
            foreach (var (bit, yaw) in new[] { (N, 90f), (E, 0f), (S, 90f), (W, 0f) })
            {
                if ((baseMask & bit) == 0) continue;
                Vector3 dir = bit == N ? Vector3.forward : bit == E ? Vector3.right : bit == S ? Vector3.back : Vector3.left;
                var arm = LabKit.Rod(t.Spin, "Arm", dir * half * 0.5f, 0.032f, half, lab.metal, yaw);
                t.Pipes.Add(arm.GetComponent<Renderer>());
            }
            var hub = LabKit.Sphere(t.Spin, "Hub", Vector3.zero, 0.042f, lab.metal);
            t.Pipes.Add(hub.GetComponent<Renderer>());
            t.Button = LabButton.Make(t.Root, "Turn the pipe");
            var tile = t;
            t.Button.Usable = () => !Done && !Assisting;
            t.Button.Blocked = () => Done ? "This pipeline is finished." : null;
            t.Button.Pressed = who => Turn(tile, true);
            m_Tiles[x, y] = t;
            m_All.Add(t);
            return t;
        }

        // ------------------------------------------------------------------ play
        protected override void ResetGame()
        {
            m_Turns = 0;
            m_AssistStep = 0f;
            foreach (var t in m_All)
            {
                if (t.OnPath)
                {
                    // Straight pipes look the same half a turn round, so they get an odd number of quarter turns.
                    int k = t.Corner ? 1 + m_Rng.Next(3) : (m_Rng.Next(2) == 0 ? 1 : 3);
                    t.Rotation = (t.Solution + k) & 3;
                }
                else t.Rotation = m_Rng.Next(4);
                t.SpinT = 1f;
                t.Spin.localRotation = Quaternion.Euler(0f, t.Rotation * 90f, 0f);
            }
            Flow();
        }

        void Turn(Tile t, bool byPlayer)
        {
            if (Done) return;
            t.SpinFrom = t.Rotation * 90f;
            t.Rotation = (t.Rotation + 1) & 3;
            t.SpinTo = t.SpinFrom + 90f;
            t.SpinT = 0f;
            if (byPlayer) m_Turns++;
            AudioDirector.Instance?.PlayAt("piece_rotate", t.Root.transform.position, 0.8f);
            Flow();
        }

        /// <summary>Follows the pipes from the capture unit; lights what is connected and checks the well.</summary>
        void Flow()
        {
            foreach (var t in m_All) t.Lit = false;
            var start = m_Tiles[0, 1];
            bool solved = false;
            if ((start.Openings & W) != 0)
            {
                var queue = new Queue<Tile>();
                start.Lit = true;
                queue.Enqueue(start);
                while (queue.Count > 0)
                {
                    var t = queue.Dequeue();
                    int open = t.Openings;
                    if (t.X == Cols - 1 && t.Y == 1 && (open & E) != 0) solved = true;
                    foreach (var (bit, dx, dy, opposite) in new[] { (N, 0, 1, S), (E, 1, 0, W), (S, 0, -1, N), (W, -1, 0, E) })
                    {
                        if ((open & bit) == 0) continue;
                        int nx = t.X + dx, ny = t.Y + dy;
                        if (nx < 0 || ny < 0 || nx >= Cols || ny >= Rows) continue;
                        var n = m_Tiles[nx, ny];
                        if (n.Lit || (n.Openings & opposite) == 0) continue;
                        n.Lit = true;
                        queue.Enqueue(n);
                    }
                }
            }
            m_Reached = 0;
            foreach (var t in m_All) if (t.Lit && t.OnPath) m_Reached++;
            foreach (var t in m_All)
                foreach (var r in t.Pipes)
                    if (t.Lit) LabKit.Tint(r, UIStyle.TealGlow, 1.6f);
                    else LabKit.ClearTint(r);
            Screen.Status.text = solved ? "<color=#35E0D0>PIPELINE COMPLETE · " + LabKit.CO2 + " STORED</color>"
                : start.Lit ? $"Flow reaches {m_Reached} of {Path.Length} pipes" : "<color=#F2714B>" + LabKit.CO2 + " is escaping: connect the first pipe</color>";
            if (solved)
            {
                LabKit.Tint(m_WellGlow, UIStyle.TealGlow, 2.4f);
                LabKit.Tint(m_SourceGlow, UIStyle.TealGlow, 1.6f);
                Complete(Assisting ? AssistScore : SpeedScore(Elapsed, Mathf.Max(0, m_Turns - 12) / 2, 8f, 30));
            }
            else
            {
                LabKit.ClearTint(m_WellGlow);
                LabKit.ClearTint(m_SourceGlow);
            }
        }

        protected override void OnTick(float dt)
        {
            Animate(dt);
            if (m_Smoke != null)
            {
                // The CO2 cloud puffs above the stack until the pipeline carries it away.
                float s = 0.06f + 0.012f * Mathf.Sin(Time.time * 2.4f);
                m_Smoke.localScale = Vector3.one * s;
                m_Smoke.gameObject.SetActive(true);
            }
            if (Assisting) StepAssist(dt);
        }

        protected override void OnDoneTick(float dt)
        {
            Animate(dt);
            if (m_Smoke != null) m_Smoke.gameObject.SetActive(false);
            float pulse = 1.4f + 0.6f * Mathf.Sin(Time.time * 4f);
            foreach (var t in m_All) if (t.Lit) foreach (var r in t.Pipes) LabKit.Tint(r, UIStyle.TealGlow, pulse);
        }

        void Animate(float dt)
        {
            foreach (var t in m_All)
            {
                if (t.SpinT >= 1f) continue;
                t.SpinT = Mathf.Min(1f, t.SpinT + Time.unscaledDeltaTime / 0.16f);
                float e = 1f - Mathf.Pow(1f - t.SpinT, 3f);
                t.Spin.localRotation = Quaternion.Euler(0f, Mathf.Lerp(t.SpinFrom, t.SpinTo, e), 0f);
            }
        }

        // ------------------------------------------------------------------ assist
        protected override void BeginAssist() => m_AssistStep = -0.4f;

        void StepAssist(float dt)
        {
            m_AssistStep += dt;
            if (m_AssistStep < 0.35f) return;
            m_AssistStep = 0f;
            // Walk the route from the source and fix the first tile that is wrong.
            foreach (var p in Path)
            {
                var t = m_Tiles[p.x, p.y];
                if (t.Openings == Rotate(t.Corner ? (N | E) : (N | S), t.Solution)) continue;
                Turn(t, false);
                return;
            }
        }

        /// <summary>QA: turns every route tile into place the way a player would (by using it).</summary>
        public System.Collections.IEnumerator QASolve()
        {
            foreach (var p in Path)
            {
                var t = m_Tiles[p.x, p.y];
                int guard = 0;
                while (!Done && t.Openings != Rotate(t.Corner ? (N | E) : (N | S), t.Solution) && guard++ < 4)
                {
                    t.Button.Interact(InteractorKind.Desktop);
                    yield return new WaitForSecondsRealtime(0.2f);
                }
            }
        }
    }
}
