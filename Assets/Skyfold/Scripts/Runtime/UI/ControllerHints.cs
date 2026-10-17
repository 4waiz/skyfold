using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Skyfold
{
    /// <summary>
    /// VR: a small card above each glove that says what that controller's buttons do right now (at the plinth,
    /// on foot, in the car, in menus). The button you need next is lit in teal. Cards show when you look at your
    /// hands, for a few seconds whenever the controls change, or always / never (Comfort settings).
    /// The gloves hide the real controllers, so without this nothing in the headset says which button is which.
    /// </summary>
    public sealed class ControllerHints : MonoBehaviour
    {
        public VRRigController rig;
        public Transform leftAnchor, rightAnchor;

        const float Scale = 0.00024f;      // canvas units to metres: a 560-unit card is about 13 cm wide
        const float LookAngle = 34f;       // a hand inside this cone around your gaze counts as looked at
        const float LookDistance = 0.95f;
        const float ShowAfterChange = 8f;  // seconds the cards stay up after the controls change

        struct Entry
        {
            public string key, label;
            public bool lit;
            public Entry(string k, string l, bool on = false) { key = k; label = l; lit = on; }
        }

        sealed class Row
        {
            public GameObject go;
            public Image chip;
            public TextMeshProUGUI key, label;
        }

        sealed class Card
        {
            public Hand hand;
            public Transform anchor;
            public RectTransform root;
            public CanvasGroup group;
            public readonly List<Row> rows = new List<Row>();
            public readonly List<Entry> shown = new List<Entry>();
            public float alpha;
        }

        Card m_Left, m_Right;
        readonly List<Entry> m_Entries = new List<Entry>();
        string m_LastState = "";
        float m_ShowUntil;

        static readonly Color ChipIdle = new Color(0.13f, 0.2f, 0.23f, 0.92f);
        static readonly Color LabelIdle = UIStyle.InkSoft;

        /// <summary>Which buttons the visible cards light, for QA ("Left:X Right:Grip").</summary>
        public string LitSummary()
        {
            var sb = new System.Text.StringBuilder();
            foreach (var card in new[] { m_Left, m_Right })
            {
                if (card == null || card.alpha < 0.5f) continue;
                foreach (var e in card.shown) if (e.lit) sb.Append(card.hand).Append(':').Append(e.key).Append(' ');
            }
            return sb.ToString().Trim();
        }
        public bool LeftVisible => m_Left != null && m_Left.alpha > 0.5f;
        public bool RightVisible => m_Right != null && m_Right.alpha > 0.5f;

        void Start()
        {
            m_Left = Build(Hand.Left, leftAnchor);
            m_Right = Build(Hand.Right, rightAnchor);
        }

        // ------------------------------------------------------------------ building
        Card Build(Hand hand, Transform anchor)
        {
            if (anchor == null) return null;
            var rt = UIKit.Rect(anchor, (hand == Hand.Left ? "Left" : "Right") + " Button Card");
            var canvas = rt.gameObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.sortingOrder = 5;
            rt.sizeDelta = new Vector2(560f, 120f);
            rt.pivot = new Vector2(0.5f, 0f); // the card grows upward from just above the hand
            rt.localScale = Vector3.one * Scale;
            var group = rt.gameObject.AddComponent<CanvasGroup>();
            group.alpha = 0f;
            group.interactable = false;
            group.blocksRaycasts = false;

            var bg = rt.gameObject.AddComponent<Image>();
            bg.sprite = UIKit.Rounded;
            bg.type = Image.Type.Sliced;
            bg.color = UIStyle.PanelGlass;
            bg.raycastTarget = false;
            var v = rt.gameObject.AddComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(22, 22, 14, 18);
            v.spacing = 8f;
            v.childControlWidth = v.childControlHeight = true;
            v.childForceExpandWidth = true;
            v.childForceExpandHeight = false;
            var fit = rt.gameObject.AddComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var title = UIKit.Text(rt, hand == Hand.Left ? "LEFT HAND" : "RIGHT HAND", 20f, UIStyle.Teal, true);
            title.characterSpacing = 10f;
            rt.gameObject.SetActive(false);
            return new Card { hand = hand, anchor = anchor, root = rt, group = group };
        }

        Row AddRow(Card card)
        {
            var rt = UIKit.Rect(card.root, "Row");
            var h = rt.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.spacing = 14f;
            h.childAlignment = TextAnchor.MiddleLeft;
            h.childControlWidth = h.childControlHeight = true;
            h.childForceExpandWidth = false;
            h.childForceExpandHeight = false;

            var chipRt = UIKit.Rect(rt, "Button");
            var chip = chipRt.gameObject.AddComponent<Image>();
            chip.sprite = UIKit.Rounded;
            chip.type = Image.Type.Sliced;
            chip.raycastTarget = false;
            var ch = chipRt.gameObject.AddComponent<HorizontalLayoutGroup>();
            ch.padding = new RectOffset(14, 14, 5, 5);
            ch.childAlignment = TextAnchor.MiddleCenter;
            ch.childControlWidth = ch.childControlHeight = true;
            ch.childForceExpandWidth = true;
            UIKit.Layout(chipRt, minHeight: 44f, preferredWidth: 128f);
            var key = UIKit.Text(chipRt, "", 28f, UIStyle.Pearl, true, TextAlignmentOptions.Center);
            key.textWrappingMode = TextWrappingModes.NoWrap;

            var label = UIKit.Text(rt, "", 31f, LabelIdle);
            UIKit.Layout(label, flexibleWidth: 1f);
            var row = new Row { go = rt.gameObject, chip = chip, key = key, label = label };
            card.rows.Add(row);
            return row;
        }

        void Fill(Card card, List<Entry> entries)
        {
            if (card == null || Same(card.shown, entries)) return;
            card.shown.Clear();
            card.shown.AddRange(entries);
            while (card.rows.Count < entries.Count) AddRow(card);
            for (int i = 0; i < card.rows.Count; i++)
            {
                var row = card.rows[i];
                bool on = i < entries.Count;
                if (row.go.activeSelf != on) row.go.SetActive(on);
                if (!on) continue;
                var e = entries[i];
                row.key.text = e.key;
                row.label.text = e.lit ? "<b>" + e.label + "</b>" : e.label;
                row.chip.color = e.lit ? UIStyle.Teal : ChipIdle;
                row.label.color = e.lit ? UIStyle.Ink : LabelIdle;
            }
        }

        static bool Same(List<Entry> a, List<Entry> b)
        {
            if (a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
                if (a[i].lit != b[i].lit || !ReferenceEquals(a[i].key, b[i].key) && a[i].key != b[i].key || !ReferenceEquals(a[i].label, b[i].label) && a[i].label != b[i].label)
                    return false;
            return true;
        }

        // ------------------------------------------------------------------ content
        /// <summary>The controls in play right now, per hand. Mirrors SkyfoldInput and the XRI Starter Assets bindings.</summary>
        void Collect(Hand hand, InputContext ctx, List<Entry> list)
        {
            list.Clear();
            var fold = FoldController.Instance;
            var car = CourierVehicle.Instance;
            var use = rig != null ? rig.GetComponent<VRUseHandler>() : null;
            string obj = MissionDirector.Instance != null && MissionDirector.Instance.CurrentObjective != null ? MissionDirector.Instance.CurrentObjective.Id ?? "" : "";
            bool teleportOnly = SettingsStore.Current.moveMode == MoveMode.TeleportOnly;
            bool left = hand == Hand.Left;

            switch (ctx)
            {
                case InputContext.Menu:
                case InputContext.Paused:
                case InputContext.Results:
                    list.Add(new Entry("Trigger", "select (point the ray)", true));
                    if (left) list.Add(new Entry("Menu", ctx == InputContext.Paused ? "resume" : "pause"));
                    else list.Add(new Entry("B", "back"));
                    break;

                case InputContext.Architect:
                {
                    bool foldNext = obj == "t.fold" || obj.EndsWith(".fold");
                    bool holding = TabletopController.Instance != null && TabletopController.Instance.Held != null;
                    list.Add(new Entry("Grip", holding ? "hold it · let go over a glowing socket" : "grab a piece", !foldNext));
                    if (left)
                    {
                        list.Add(new Entry("X", "fold down into the street", foldNext));
                        list.Add(new Entry("Y", "objectives"));
                        list.Add(new Entry("Menu", "pause"));
                    }
                    else
                    {
                        list.Add(new Entry("Wrist", "twist to turn a held piece", holding));
                        list.Add(new Entry("A", "hold to aim a teleport, let go"));
                        list.Add(new Entry("B", "back"));
                    }
                    break;
                }

                case InputContext.OnFoot:
                case InputContext.Cutscene:
                {
                    bool station = fold != null && fold.InStreet && fold.StationInRange != null;
                    bool target = use != null && (left ? use.LeftTarget : use.RightTarget) != null;
                    bool useStep = obj == "t.enter" || obj == "t.cell" || obj.StartsWith("d.") && obj != "d.route";
                    bool walkStep = obj == "t.walk";
                    if (left)
                    {
                        if (!teleportOnly) list.Add(new Entry("Stick", "walk", walkStep));
                        list.Add(new Entry("Trigger", "use what you point at", target));
                        list.Add(new Entry("Grip", "grab"));
                        list.Add(new Entry("X", "fold up (at a Fold Station)", station));
                        list.Add(new Entry("Y", "objectives"));
                        list.Add(new Entry("Menu", "pause"));
                    }
                    else
                    {
                        list.Add(new Entry("A", "hold to aim a teleport, let go", walkStep || teleportOnly && !target));
                        list.Add(new Entry("Stick", "turn"));
                        list.Add(new Entry("Trigger", "use what you point at", target || useStep && !station));
                        list.Add(new Entry("Grip", "grab"));
                        list.Add(new Entry("B", "back"));
                    }
                    break;
                }

                case InputContext.Driving:
                case InputContext.RemoteDriving:
                {
                    bool stopped = car == null || Mathf.Abs(car.Speed) < 0.6f;
                    if (left)
                    {
                        list.Add(new Entry("Stick", "steer", !stopped));
                        list.Add(new Entry("Trigger", "brake · hold at a stop to reverse"));
                        list.Add(new Entry("X", "hold: car back on the road"));
                        list.Add(new Entry("Y", "objectives"));
                    }
                    else
                    {
                        list.Add(new Entry("Trigger", "accelerate", true));
                        list.Add(new Entry("B", "climb out (when stopped)", stopped && obj != "t.drive"));
                        list.Add(new Entry("A", "horn"));
                    }
                    break;
                }
            }
        }

        // ------------------------------------------------------------------ per frame
        void LateUpdate()
        {
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            bool vr = rigs != null && rigs.Mode == PlayMode.VR && input != null && rig != null && rig.Camera != null;
            var mode = SettingsStore.Current.buttonHints;
            var ctx = input != null ? input.Context : InputContext.Menu;
            bool paused = GameRoot.Instance != null && GameRoot.Instance.IsPaused;
            if (paused) ctx = InputContext.Paused;

            // Pop the cards up for a few seconds whenever the controls change (entering VR, the plinth, the
            // street, the car, a menu) and whenever the next step needs a different button.
            string obj = MissionDirector.Instance != null && MissionDirector.Instance.CurrentObjective != null ? MissionDirector.Instance.CurrentObjective.Id : "";
            string state = vr ? ctx + "|" + obj : "";
            if (state != m_LastState)
            {
                m_LastState = state;
                if (vr) m_ShowUntil = Time.unscaledTime + ShowAfterChange;
            }

            Tick(m_Left, vr, mode, ctx);
            Tick(m_Right, vr, mode, ctx);
        }

        void Tick(Card card, bool vr, ButtonHints mode, InputContext ctx)
        {
            if (card == null) return;
            var head = vr ? rig.Head : null;
            bool want = vr && mode != ButtonHints.Off && ctx != InputContext.Cutscene && card.anchor.gameObject.activeInHierarchy;
            if (want && mode == ButtonHints.WhenLookingAtHands)
                want = Time.unscaledTime < m_ShowUntil || LookingAt(head, card.anchor);

            float goal = want ? 1f : 0f;
            card.alpha = Mathf.MoveTowards(card.alpha, goal, Time.unscaledDeltaTime * 5f);
            bool show = card.alpha > 0.001f;
            if (card.root.gameObject.activeSelf != show) card.root.gameObject.SetActive(show);
            if (!show) return;
            card.group.alpha = Mathf.SmoothStep(0f, 1f, card.alpha);

            Collect(card.hand, ctx, m_Entries);
            Fill(card, m_Entries);

            // Float just above the top of the controller (the handle runs along the grip pose's +Z), nudged
            // outward so the two cards never overlap, and always turned to face your eyes, upright.
            Vector3 top = card.anchor.position + card.anchor.forward * 0.075f;
            Vector3 side = Vector3.ProjectOnPlane(head.right, Vector3.up).normalized * (card.hand == Hand.Left ? -0.045f : 0.045f);
            Vector3 pos = top + Vector3.up * 0.05f + side;
            Vector3 toCard = pos - head.position;
            if (toCard.sqrMagnitude < 0.0001f) return;
            card.root.SetPositionAndRotation(pos, Quaternion.LookRotation(toCard.normalized, Vector3.up));
        }

        static bool LookingAt(Transform head, Transform hand)
        {
            if (head == null || hand == null) return false;
            Vector3 to = hand.position - head.position;
            float d = to.magnitude;
            return d < LookDistance && d > 0.05f && Vector3.Angle(head.forward, to) < LookAngle;
        }
    }
}
