using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>The airfield substation: a cell in its socket powers the island (lights, terminal, aircraft).</summary>
    public sealed class Substation : MonoBehaviour
    {
        public static Substation Instance { get; private set; }

        public CellSocket socket;
        public List<Renderer> powerLights = new List<Renderer>();
        public List<Light> islandLights = new List<Light>();
        public List<Renderer> islandWindows = new List<Renderer>();

        CityState m_City;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        void Awake()
        {
            Instance = this;
            m_Block = new MaterialPropertyBlock();
            if (socket != null) socket.Inserted += OnCell;
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (socket != null) socket.Inserted -= OnCell;
            if (m_City != null) m_City.FlagChanged -= OnFlag;
        }

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.FlagChanged -= OnFlag;
            m_City = city;
            m_City.FlagChanged += OnFlag;
            Apply(m_City.GetFlag(Flags.SubstationPowered));
        }

        void OnCell(CellSocket s)
        {
            if (m_City == null) return;
            m_City.SetFlag(Flags.SubstationPowered, true);
            AudioDirector.Instance?.PlayAt("power_transfer", s.transform.position, 1f, 1f, 6f);
            AudioDirector.Instance?.PlayAt("substation_on", transform.position, 1f, 1f, 10f);
            NuriCompanion.Instance?.React(NuriMood.Celebrate, s.transform);
        }

        void OnFlag(string key, bool value)
        {
            if (key == Flags.SubstationPowered) Apply(value);
        }

        void Apply(bool on)
        {
            foreach (var r in powerLights)
            {
                if (r == null) continue;
                r.GetPropertyBlock(m_Block);
                m_Block.SetColor(EmissionId, on ? new Color(0.21f, 0.88f, 0.82f) * 4f : Color.black);
                r.SetPropertyBlock(m_Block);
            }
            foreach (var l in islandLights) if (l != null) l.enabled = on;
            foreach (var r in islandWindows) SetEmissiveSlots(r, on ? new Color(1f, 0.85f, 0.6f) * 2.2f : Color.black, m_Block);
        }

        /// <summary>Applies emission only to the window/lamp material slots of a multi-material renderer.</summary>
        public static void SetEmissiveSlots(Renderer r, Color emission, MaterialPropertyBlock block)
        {
            if (r == null) return;
            var mats = r.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
            {
                if (mats[i] == null) continue;
                string n = mats[i].name;
                if (n != "SKY_Light" && n != "SKY_Glass") continue;
                r.GetPropertyBlock(block, i);
                block.SetColor(EmissionId, n == "SKY_Glass" ? emission * 0.35f : emission);
                r.SetPropertyBlock(block, i);
            }
        }
    }
}
