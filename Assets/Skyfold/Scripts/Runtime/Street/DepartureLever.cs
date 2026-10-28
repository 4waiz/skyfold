using UnityEngine;

namespace Skyfold
{
    /// <summary>Clears the last flight. Only works once every departure condition is actually met.</summary>
    public sealed class DepartureLever : WorldInteractable
    {
        public Transform lever;
        public AircraftSequence aircraft;
        Quaternion m_Base;
        bool m_HasBase;
        float m_Angle;

        CityState City => GameRoot.Instance != null ? GameRoot.Instance.City : null;
        bool Cleared => City != null && City.GetFlag(Flags.DepartureCleared);

        public override bool CanInteract(InteractorKind who) => base.CanInteract(who) && !Cleared && aircraft != null && aircraft.ConditionsMet;
        public override string Prompt => "Clear the clean flight for take-off";

        public override string BlockedReason
        {
            get
            {
                if (Cleared) return "The flight is already cleared.";
                if (aircraft == null) return null;
                var missing = aircraft.MissingConditions();
                return string.IsNullOrEmpty(missing) ? null : "Not yet: " + missing + ".";
            }
        }

        public override void Interact(InteractorKind who)
        {
            if (City == null || Cleared) return;
            City.SetFlag(Flags.DepartureCleared, true);
            AudioDirector.Instance?.PlayAt("switch_lever", transform.position, 1f, 0.85f);
        }

        void Update()
        {
            float target = Cleared ? 160f : 0f; // same switch box: up = off, thrown down = on
            m_Angle = Mathf.MoveTowards(m_Angle, target, Time.deltaTime * 320f);
            if (lever != null) { if (!m_HasBase) { m_Base = lever.localRotation; m_HasBase = true; } lever.localRotation = m_Base * Quaternion.Euler(m_Angle, 0f, 0f); }
        }
    }
}
