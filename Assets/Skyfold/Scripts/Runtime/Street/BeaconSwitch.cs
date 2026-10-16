using UnityEngine;

namespace Skyfold
{
    /// <summary>A runway beacon switch (or the demo's master switch). Needs substation power.</summary>
    public sealed class BeaconSwitch : WorldInteractable
    {
        public string flagKey = "beacon.1";
        public Transform lever;
        public float offAngle = 0f, onAngle = 160f; // modelled up = off; thrown out and down = on

        Quaternion m_Base;
        bool m_HasBase;
        float m_Angle;

        CityState City => GameRoot.Instance != null ? GameRoot.Instance.City : null;
        bool IsOn => City != null && City.GetFlag(flagKey);
        bool Powered => City != null && City.GetFlag(Flags.SubstationPowered);

        public override bool CanInteract(InteractorKind who) => base.CanInteract(who) && !IsOn && Powered;
        public override string Prompt => "Switch on the runway beacons";
        public override string BlockedReason => IsOn ? "These beacons are already on." : (!Powered ? "No power yet. The substation needs a cell." : null);

        public override void Interact(InteractorKind who)
        {
            if (City == null || IsOn) return;
            City.SetFlag(flagKey, true);
            AudioDirector.Instance?.PlayAt("switch_lever", transform.position, 1f);
            NuriCompanion.Instance?.React(NuriMood.Happy, transform);
        }

        void Update()
        {
            float target = IsOn ? onAngle : offAngle;
            m_Angle = Mathf.MoveTowards(m_Angle, target, Time.deltaTime * 420f);
            if (lever != null) { if (!m_HasBase) { m_Base = lever.localRotation; m_HasBase = true; } lever.localRotation = m_Base * Quaternion.Euler(m_Angle, 0f, 0f); }
        }
    }
}
