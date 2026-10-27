using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Mini-game 1, "Power the city 24/7": drop four of five energy blocks into the grid so the city has enough
    /// power by day and by night with zero emissions. Solar gives 2 by day, nuclear 1 day and night, a battery moves
    /// 2 from day to night, gas gives 1 day and night but emits CO2. The only clean answer is solar, solar, nuclear,
    /// battery; solar, solar, gas, battery keeps the lights on but is called out for its emissions.
    /// </summary>
    public sealed class EnergyMixGame : LabGame
    {
        public enum Kind { Solar, Nuclear, Battery, Gas }

        public const int Demand = 3;
        const int SlotCount = 4;
        const float SnapRadius = 0.11f;

        sealed class Slot
        {
            public Transform Point;
            public Renderer Ring;
            public LabToken Occupant;
        }

        readonly List<LabToken> m_Tokens = new List<LabToken>();
        readonly List<Slot> m_Slots = new List<Slot>();
        Transform m_DayFill, m_NightFill, m_Co2Fill;
        TextMeshPro m_DayText, m_NightText, m_Co2Text;
        readonly List<Renderer> m_CityWindows = new List<Renderer>();
        string m_LastWrongCombo;
        bool m_SaidNight, m_SaidGas;
        LabToken m_Held;
        Slot m_Preview;
        float m_AssistStep;
        int m_Day, m_Night, m_Co2;

        public override string Title => "Power the city 24/7";
        public override float Budget => 60f;
        public override string FactLine => "lab.fact.mix";
        public override string FactText =>
            "<b><color=#F5C242>Grid balanced, zero emissions!</color></b>\n\n" +
            "Nuclear runs day and night; solar plus batteries covers the rest.\n" +
            "<size=85%>In Abu Dhabi, ADNOC can take up to 100% of its grid power from clean nuclear and solar plants, including Barakah.</size>";
        public override string Progress => $"Day {m_Day}/{Demand} · Night {m_Night}/{Demand} · {LabKit.CO2} {m_Co2}";
        public override string ResultLine => Assisted ? "Power the city: solved with help" : $"Power the city: solved in {Mathf.RoundToInt(SinceSolvedTime)} s";
        float SinceSolvedTime => Elapsed - SinceDone;

        public static int DayOf(Kind k) => k == Kind.Solar ? 2 : k == Kind.Battery ? -2 : 1;
        public static int NightOf(Kind k) => k == Kind.Solar ? 0 : k == Kind.Battery ? 2 : 1;
        public static int Co2Of(Kind k) => k == Kind.Gas ? 1 : 0;

        // ------------------------------------------------------------------ build
        protected override void Build()
        {
            var lab = Lab;
            Screen = LabScreen.Make(lab, Board, "POWER THE CITY 24/7", lab.solar);
            Screen.Body.text =
                "Fill all <b>4 slots</b>: <b>3</b> by day, <b>3</b> at night, <b>zero " + LabKit.CO2 + "</b>.\n" +
                "<color=#F5C242>SOLAR</color>  day 2 · night 0\n" +
                "<color=#B9A8FF>NUCLEAR</color>  day 1 · night 1\n" +
                "<color=#6FE09A>BATTERY</color>  moves 2 from day to night\n" +
                "<color=#C9CDD0>GAS</color>  day 1 · night 1 · emits " + LabKit.CO2;

            // Meters on the right half of the screen.
            var c = Screen.Content;
            m_DayFill = Meter(c, "DAY", 0.095f, lab.solar, out m_DayText);
            m_NightFill = Meter(c, "NIGHT", 0.04f, lab.blue, out m_NightText);
            m_Co2Fill = Meter(c, LabKit.CO2, -0.015f, lab.coral, out m_Co2Text);

            // A little skyline on the screen whose windows light up when the grid is balanced.
            for (int i = 0; i < 5; i++)
            {
                float h = 0.035f + (i % 3) * 0.012f;
                var b = LabKit.Box(Screen.Content, "Building " + i, new Vector3(0.36f + i * 0.055f, -0.15f + h * 0.5f, -0.004f), new Vector3(0.045f, h, 0.006f), lab.ink);
                LabKit.Tint(b.GetComponent<Renderer>(), new Color(0.2f, 0.27f, 0.31f));
                var w = LabKit.Box(Screen.Content, "Windows " + i, new Vector3(0.36f + i * 0.055f, -0.15f + h * 0.55f, -0.008f), new Vector3(0.026f, h * 0.6f, 0.003f), lab.lamp);
                m_CityWindows.Add(w.GetComponent<Renderer>());
            }

            // The grid: four slots on a power line.
            LabKit.Box(Board, "Grid Line", new Vector3(0f, 0.012f, -0.04f), new Vector3(1.0f, 0.008f, 0.012f), lab.metal);
            LabKit.Label(Board, "CITY GRID", new Vector3(0f, 0.017f, 0.08f), LabKit.Flat, 0.42f, UIStyle.Teal, 0.6f, 0.06f, true);
            for (int i = 0; i < SlotCount; i++)
            {
                var p = LabKit.Node(Board, "Slot " + i, new Vector3(-0.39f + i * 0.26f, 0.012f, -0.04f)).transform;
                var pad = LabKit.Cylinder(p, "Pad", Vector3.zero, 0.15f, 0.008f, lab.pearl);
                var ring = LabKit.Cylinder(p, "Ring", new Vector3(0f, 0.002f, 0f), 0.165f, 0.006f, lab.tealGlow);
                pad.transform.localPosition = new Vector3(0f, 0.003f, 0f);
                m_Slots.Add(new Slot { Point = p, Ring = ring.GetComponent<Renderer>() });
            }

            // The tray of blocks at the front edge.
            LabKit.Label(Board, "ENERGY BLOCKS", new Vector3(0f, 0.012f, -0.235f), LabKit.Flat, 0.32f, UIStyle.InkSoft, 0.6f, 0.05f, true);
            var kinds = new[] { Kind.Solar, Kind.Nuclear, Kind.Battery, Kind.Solar, Kind.Gas };
            for (int i = 0; i < kinds.Length; i++)
                m_Tokens.Add(MakeToken(kinds[i], i, new Vector3(-0.48f + i * 0.24f, 0.008f, -0.36f)));
        }

        Transform Meter(Transform parent, string label, float y, Material fill, out TextMeshPro value)
        {
            var lab = Lab;
            LabKit.Label(parent, label, new Vector3(0.08f, y, 0f), Quaternion.identity, 0.3f, UIStyle.PearlDeep, 0.12f, 0.05f, true, TextAlignmentOptions.Right);
            const float w = 0.34f;
            float x0 = 0.16f;
            var bg = LabKit.Box(parent, label + " Rail", new Vector3(x0 + w * 0.5f, y, -0.002f), new Vector3(w, 0.03f, 0.004f), lab.ink);
            LabKit.Tint(bg.GetComponent<Renderer>(), new Color(0.24f, 0.31f, 0.35f));
            var pivot = LabKit.Node(parent, label + " Fill", new Vector3(x0, y, -0.005f)).transform;
            LabKit.Box(pivot, "Bar", new Vector3(0.5f, 0f, 0f), new Vector3(1f, 0.026f, 0.004f), fill);
            pivot.localScale = new Vector3(0.0001f, 1f, 1f);
            if (label != LabKit.CO2)
            {
                // Target tick at the demand line (3 of 4).
                LabKit.Box(parent, label + " Target", new Vector3(x0 + w * 0.75f, y, -0.007f), new Vector3(0.005f, 0.042f, 0.004f), lab.pearl);
            }
            value = LabKit.Label(parent, "", new Vector3(x0 + w + 0.07f, y, 0f), Quaternion.identity, 0.3f, UIStyle.Pearl, 0.12f, 0.05f, true, TextAlignmentOptions.Left);
            return pivot;
        }

        LabToken MakeToken(Kind kind, int index, Vector3 localPos)
        {
            var lab = Lab;
            string name = kind.ToString().ToUpperInvariant();
            var root = LabKit.Node(Board, "Block " + name + " " + index, localPos);
            var mat = kind == Kind.Solar ? lab.solar : kind == Kind.Nuclear ? lab.nuclear : kind == Kind.Battery ? lab.battery : lab.gas;
            var body = LabKit.Box(root.transform, "Body", new Vector3(0f, 0.025f, 0f), new Vector3(0.11f, 0.05f, 0.11f), mat);
            body.AddComponent<BoxCollider>();
            // A small icon on top so the kinds read apart at a glance, not by colour alone.
            switch (kind)
            {
                case Kind.Solar:
                    LabKit.Prim(PrimitiveType.Cube, root.transform, "Panel", new Vector3(0f, 0.056f, 0.022f), new Vector3(0.085f, 0.004f, 0.045f), lab.blue, false, Quaternion.Euler(-20f, 0f, 0f));
                    break;
                case Kind.Nuclear:
                    LabKit.Cylinder(root.transform, "Tower", new Vector3(0f, 0.07f, 0.025f), 0.035f, 0.04f, lab.pearl);
                    break;
                case Kind.Battery:
                    LabKit.Box(root.transform, "Plus", new Vector3(-0.025f, 0.056f, 0.03f), new Vector3(0.018f, 0.008f, 0.018f), lab.metal);
                    LabKit.Box(root.transform, "Minus", new Vector3(0.025f, 0.056f, 0.03f), new Vector3(0.018f, 0.008f, 0.018f), lab.metal);
                    break;
                case Kind.Gas:
                    LabKit.Cylinder(root.transform, "Stack", new Vector3(0.025f, 0.075f, 0.025f), 0.02f, 0.05f, lab.metal);
                    LabKit.Sphere(root.transform, "Smoke", new Vector3(0.025f, 0.11f, 0.025f), 0.028f, lab.gas);
                    break;
            }
            LabKit.Label(root.transform, name, new Vector3(0f, 0.0515f, -0.025f), LabKit.Flat, 0.2f, UIStyle.Ink, 0.11f, 0.03f, true);

            var tok = root.AddComponent<LabToken>();
            tok.tokenId = name.ToLowerInvariant() + index;
            tok.kind = (int)kind;
            tok.displayName = name;
            tok.homePosition = root.transform.position;
            tok.homeRotation = root.transform.rotation;
            LabKit.SetLayer(root, "Interactable");
            tok.Setup();
            tok.CanPick = t => !Done && !Assisting;
            tok.Picked = OnPicked;
            tok.Dropped = OnDropped;
            return tok;
        }

        // ------------------------------------------------------------------ play
        protected override void ResetGame()
        {
            foreach (var s in m_Slots) s.Occupant = null;
            foreach (var t in m_Tokens)
            {
                t.ForceRelease();
                t.SetImmediate(t.homePosition, t.homeRotation);
                t.SetGrabbable(true);
            }
            m_Held = null;
            m_Preview = null;
            m_LastWrongCombo = null;
            m_SaidNight = m_SaidGas = false;
            m_AssistStep = 0f;
            Evaluate(false);
        }

        public override void ReleaseAll()
        {
            foreach (var t in m_Tokens) if (t.Held) t.ForceRelease();
            m_Held = null;
            HUDMessages.SetHint(null);
        }

        void OnPicked(LabToken t)
        {
            m_Held = t;
            foreach (var s in m_Slots) if (s.Occupant == t) s.Occupant = null;
            Evaluate(false);
        }

        void OnDropped(LabToken t)
        {
            if (m_Held == t) m_Held = null;
            HUDMessages.SetHint(null);
            var slot = NearestSlot(t.transform.position);
            if (slot == null || Done || Assisting)
            {
                t.GoHome();
                AudioDirector.Instance?.PlayAt("piece_drop", t.transform.position, 0.6f);
                return;
            }
            if (slot.Occupant != null && slot.Occupant != t) slot.Occupant.GoHome();
            slot.Occupant = t;
            t.MoveTo(slot.Point.position, slot.Point.rotation, 0.18f);
            AudioDirector.Instance?.PlayAt("socket_snap", slot.Point.position, 1f);
            Evaluate(true);
        }

        Slot NearestSlot(Vector3 world)
        {
            Slot best = null;
            float bestD = SnapRadius;
            foreach (var s in m_Slots)
            {
                Vector3 d = world - s.Point.position;
                if (d.y > 0.3f) continue;
                d.y = 0f;
                float m = d.magnitude;
                if (m < bestD) { bestD = m; best = s; }
            }
            return best;
        }

        void Evaluate(bool placed)
        {
            m_Day = m_Night = m_Co2 = 0;
            int filled = 0;
            var combo = new List<string>();
            foreach (var s in m_Slots)
            {
                if (s.Occupant == null) continue;
                var k = (Kind)s.Occupant.kind;
                m_Day += DayOf(k);
                m_Night += NightOf(k);
                m_Co2 += Co2Of(k);
                filled++;
                combo.Add(k.ToString());
            }
            combo.Sort();
            bool dayOk = m_Day >= Demand, nightOk = m_Night >= Demand, clean = m_Co2 == 0;
            UpdateMeters();

            string status;
            if (filled == 0) status = "Drag energy blocks into the grid slots";
            else if (dayOk && nightOk && clean && filled == SlotCount) status = "<color=#6FE09A>GRID BALANCED · ZERO EMISSIONS</color>";
            else if (filled < SlotCount) status = $"{filled} of {SlotCount} slots filled";
            else if (!dayOk) status = "<color=#F2714B>Not enough power by day</color>";
            else if (!nightOk) status = "<color=#F2714B>The city goes dark at night</color>";
            else status = "<color=#F2714B>Lights on, but it emits " + LabKit.CO2 + "</color>";
            Screen.Status.text = status;

            if (!placed || Done) return;
            if (dayOk && nightOk && clean && filled == SlotCount)
            {
                SetWindows(true);
                Complete(Assisting ? AssistScore : SpeedScore(Elapsed, Mistakes, 8f, 60));
                return;
            }
            if (filled < SlotCount) return;
            string key = string.Join(",", combo);
            if (key == m_LastWrongCombo) return;
            m_LastWrongCombo = key;
            Mistakes++;
            AudioDirector.Instance?.PlayUI("socket_reject", 0.7f);
            NuriCompanion.Instance?.React(NuriMood.Concern, Board);
            if (dayOk && nightOk && !clean && !m_SaidGas) { m_SaidGas = true; DialogueDirector.Instance?.Play("lab.mix.gas", "lab.mix", 10f); }
            else if (!nightOk && !m_SaidNight) { m_SaidNight = true; DialogueDirector.Instance?.Play("lab.mix.night", "lab.mix", 10f); }
            HUDMessages.Toast(!dayOk ? "Not enough daytime power yet. Solar is strongest by day."
                : !nightOk ? "Night needs power too. Solar sleeps after sunset."
                : "That works, but gas emits " + LabKit.CO2 + ". Find a zero-carbon swap.", true);
        }

        void UpdateMeters()
        {
            SetFill(m_DayFill, m_Day / 4f);
            SetFill(m_NightFill, m_Night / 4f);
            SetFill(m_Co2Fill, m_Co2 / 2f);
            m_DayText.text = Mathf.Max(0, m_Day) + "/" + Demand;
            m_NightText.text = Mathf.Max(0, m_Night) + "/" + Demand;
            m_Co2Text.text = m_Co2.ToString();
            m_DayText.color = m_Day >= Demand ? UIStyle.TealGlow : UIStyle.Pearl;
            m_NightText.color = m_Night >= Demand ? UIStyle.TealGlow : UIStyle.Pearl;
            m_Co2Text.color = m_Co2 == 0 ? UIStyle.TealGlow : UIStyle.Coral;
            SetWindows(m_Day >= Demand && m_Night >= Demand && m_Co2 == 0);
        }

        static void SetFill(Transform fill, float v)
        {
            v = Mathf.Clamp01(v);
            fill.localScale = new Vector3(Mathf.Max(0.0001f, v * 0.34f), 1f, 1f);
        }

        void SetWindows(bool lit)
        {
            foreach (var w in m_CityWindows)
                if (lit) LabKit.ClearTint(w);
                else LabKit.Tint(w, new Color(0.16f, 0.2f, 0.23f));
        }

        protected override void OnTick(float dt)
        {
            // Preview: the slot under a held block glows.
            Slot preview = null;
            if (m_Held != null) preview = NearestSlot(m_Held.transform.position);
            if (preview != m_Preview) m_Preview = preview;
            float pulse = 1.2f + 0.8f * Mathf.Sin(Time.time * 3.2f);
            foreach (var s in m_Slots)
            {
                bool hot = s == m_Preview;
                LabKit.Tint(s.Ring, hot ? UIStyle.Gold : UIStyle.TealGlow, hot ? 2.6f : (s.Occupant == null ? pulse : 0.6f));
            }
            if (m_Held != null) HUDMessages.SetHint(preview != null ? "Let go to plug it into the grid." : "Hold it over a glowing grid slot.");

            if (Assisting) StepAssist(dt);
        }

        protected override void OnDoneTick(float dt)
        {
            foreach (var s in m_Slots) LabKit.Tint(s.Ring, UIStyle.Gold, 1.6f + 0.6f * Mathf.Sin(Time.time * 4f));
        }

        // ------------------------------------------------------------------ assist
        protected override void BeginAssist()
        {
            foreach (var t in m_Tokens) t.SetGrabbable(false);
            foreach (var s in m_Slots) if (s.Occupant != null) { s.Occupant.GoHome(); s.Occupant = null; }
            m_AssistStep = -0.5f;
            Evaluate(false);
        }

        void StepAssist(float dt)
        {
            m_AssistStep += dt;
            if (m_AssistStep < 0.7f) return;
            m_AssistStep = 0f;
            var want = new[] { Kind.Solar, Kind.Solar, Kind.Nuclear, Kind.Battery };
            for (int i = 0; i < SlotCount; i++)
            {
                if (m_Slots[i].Occupant != null) continue;
                foreach (var t in m_Tokens)
                {
                    if ((Kind)t.kind != want[i] || IsPlaced(t)) continue;
                    m_Slots[i].Occupant = t;
                    t.MoveTo(m_Slots[i].Point.position, m_Slots[i].Point.rotation, 0.45f);
                    AudioDirector.Instance?.PlayAt("socket_snap", m_Slots[i].Point.position, 0.8f);
                    Evaluate(true);
                    return;
                }
            }
        }

        bool IsPlaced(LabToken t)
        {
            foreach (var s in m_Slots) if (s.Occupant == t) return true;
            return false;
        }

        /// <summary>QA: drops a block of this kind into slot i (as a player would).</summary>
        public bool QAPlace(Kind kind, int slot)
        {
            foreach (var t in m_Tokens)
            {
                if ((Kind)t.kind != kind || IsPlaced(t)) continue;
                if (!t.BeginDesktopHold()) return false;
                t.SetImmediate(m_Slots[slot].Point.position + Vector3.up * 0.05f, t.homeRotation);
                t.EndDesktopHold();
                return true;
            }
            return false;
        }
    }
}
