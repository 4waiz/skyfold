using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// The full-scale counterpart of a socket. Shows the broken stub when empty, or the module the
    /// player placed on the miniature, with an assembly animation. Same CityState, real colliders.
    /// </summary>
    public sealed class FullScaleSlot : MonoBehaviour
    {
        [System.Serializable]
        public sealed class Variant
        {
            public ModuleType type;
            public GameObject root;
        }

        public string socketId;
        public GameObject brokenStub;
        public List<Variant> variants = new List<Variant>();
        public Light buildLight;
        public float buildDuration = 1.6f;

        CityState m_City;
        GameObject m_Shown;
        float m_BuildT = 1f;
        bool m_AnimateNext;
        Vector3 m_ShownBase;

        public bool IsBuilt => m_City != null && !m_City.GetPlacement(socketId).IsEmpty;

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.SocketChanged -= OnChanged;
            m_City = city;
            m_City.SocketChanged += OnChanged;
            Refresh(false);
        }

        void OnDestroy()
        {
            if (m_City != null) m_City.SocketChanged -= OnChanged;
        }

        /// <summary>Animate the next change (player action). Resets and checkpoints apply instantly.</summary>
        public void AnimateNextChange() => m_AnimateNext = true;

        void OnChanged(string id)
        {
            if (id != socketId) return;
            Refresh(m_AnimateNext);
            m_AnimateNext = false;
        }

        public void Refresh(bool animate)
        {
            var p = m_City.GetPlacement(socketId);
            GameObject target = null;
            if (!p.IsEmpty)
                foreach (var v in variants)
                    if (v.type == p.Type && v.root != null) { target = v.root; break; }

            foreach (var v in variants)
                if (v.root != null && v.root != target) v.root.SetActive(false);
            if (brokenStub != null) brokenStub.SetActive(target == null);

            if (target != null)
            {
                target.transform.localRotation = Quaternion.Euler(0f, p.Rotation * 90f, 0f);
                target.transform.localPosition = Vector3.zero;
                target.SetActive(true);
                m_ShownBase = Vector3.zero;
                if (animate)
                {
                    m_BuildT = 0f;
                    AudioDirector.Instance?.PlayAt("bridge_assemble", transform.position + Vector3.up * 2f, 1f, 1f, 12f);
                }
                else m_BuildT = 1f;
            }
            m_Shown = target;
            ApplyBuild();
        }

        void Update()
        {
            if (m_BuildT >= 1f) return;
            m_BuildT = Mathf.Min(1f, m_BuildT + Time.deltaTime / buildDuration);
            ApplyBuild();
        }

        void ApplyBuild()
        {
            if (m_Shown != null)
            {
                float e = 1f - Mathf.Pow(1f - m_BuildT, 3f);
                // Rise out of the water with a gentle overshoot, like a folding structure locking in.
                float y = Mathf.Lerp(-5f, 0f, e) + Mathf.Sin(e * Mathf.PI) * 0.35f;
                m_Shown.transform.localPosition = m_ShownBase + new Vector3(0f, y, 0f);
                float s = Mathf.Lerp(0.85f, 1f, e);
                m_Shown.transform.localScale = new Vector3(1f, s, 1f);
            }
            if (buildLight != null)
            {
                bool on = m_BuildT < 1f;
                buildLight.enabled = on;
                if (on) buildLight.intensity = Mathf.Sin(m_BuildT * Mathf.PI) * 40f;
            }
        }
    }