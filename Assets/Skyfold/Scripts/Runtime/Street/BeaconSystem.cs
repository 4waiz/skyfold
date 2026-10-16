using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Runway edge beacons in groups, one group per switch. Beacons only light when the substation
    /// has power. In the demo a single master switch lights every group.
    /// </summary>
    public sealed class BeaconSystem : MonoBehaviour
    {
        public static BeaconSystem Instance { get; private set; }

        [System.Serializable]
        public sealed class Group
        {
            public List<Renderer> lenses = new List<Renderer>();
            public List<Light> lights = new List<Light>();
        }

        public List<Group> groups = new List<Group>();
        public List<BeaconSwitch> switches = new List<BeaconSwitch>();
        public BeaconSwitch masterSwitch;

        CityState m_City;
        readonly bool[] m_On = new bool[8];
        bool m_MasterMode;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        public int Total => m_MasterMode ? 1 : switches.Count;
        public int LitCount
        {
            get
            {
                if (m_City == null) return 0;
                if (m_MasterMode) return m_City.GetFlag(Flags.BeaconPrefix + "master") ? 1 : 0;
                int n = 0;
                for (int i = 0; i < switches.Count; i++) if (m_City.GetFlag(Flags.BeaconPrefix + (i + 1))) n++;
                return n;
            }
        }
        public bool AllLit => Total > 0 && LitCount >= Total;
        public bool Powered => m_City != null && m_City.GetFlag(Flags.SubstationPowered);

        void Awake()
        {
            Instance = this;
            m_Block = new MaterialPropertyBlock();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (m_City != null) m_City.FlagChanged -= OnFlag;
        }

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.FlagChanged -= OnFlag;
            m_City = city;
            m_City.FlagChanged += OnFlag;
        }

        /// <summary>Episode 3 uses three switches; the demo uses one master switch.</summary>
        public void Configure(bool masterMode)
        {
            m_MasterMode = masterMode;
            for (int i = 0; i < switches.Count; i++) if (switches[i] != null) switches[i].gameObject.SetActive(!masterMode);
            if (masterSwitch != null) masterSwitch.gameObject.SetActive(masterMode);
            Refresh(true);
        }

        void OnFlag(string key, bool value)
        {
            if (key.StartsWith(Flags.BeaconPrefix) || key == Flags.SubstationPowered) Refresh(false);
        }

        public void Refresh(bool instant)
        {
            for (int g = 0; g < groups.Count; g++)
            {
                bool on = Powered && (m_MasterMode ? m_City.GetFlag(Flags.BeaconPrefix + "master") : m_City.GetFlag(Flags.BeaconPrefix + (g + 1)));
                if (on == m_On[g]) continue;
                m_On[g] = on;
                if (on && !instant) StartCoroutine(Sweep(groups[g]));
                else SetGroup(groups[g], on, 1f);
            }
        }

        IEnumerator Sweep(Group g)
        {
            for (int i = 0; i < g.lenses.Count; i++)
            {
                SetLens(g.lenses[i], true);
                if (i < g.lights.Count && g.lights[i] != null) g.lights[i].enabled = true;
                if (i % 2 == 0) AudioDirector.Instance?.PlayAt("beacon_on", g.lenses[i].transform.position, 0.7f, 1f + i * 0.04f);
                yield return new WaitForSeconds(0.09f);
            }
        }

        void SetGroup(Group g, bool on, float intensity)
        {
            foreach (var l in g.lenses) SetLens(l, on);
            foreach (var l in g.lights) if (l != null) l.enabled = on;
        }

        void SetLens(Renderer r, bool on)
        {
            if (r == null) return;
            r.GetPropertyBlock(m_Block);
            m_Block.SetColor(EmissionId, on ? new Color(1f, 0.82f, 0.42f) * 6f : new Color(0.05f, 0.05f, 0.05f));
            r.SetPropertyBlock(m_Block);
        }

        public Transform NextSwitch()
        {
            if (m_MasterMode) return masterSwitch != null ? masterSwitch.transform : null;
            for (int i = 0; i < switches.Count; i++)
                if (switches[i] != null && !m_City.GetFlag(Flags.BeaconPrefix + (i + 1))) return switches[i].transform;
            return null;
        }
    }
}
