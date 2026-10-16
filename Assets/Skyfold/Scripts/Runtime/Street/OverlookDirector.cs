using System.Collections;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// VR comfort "Remote Drive": the player stands on a fixed elevated overlook and drives the
    /// same car remotely, so there is no artificial vehicle motion. Overlooks change only with a fade.
    /// </summary>
    public sealed class OverlookDirector : MonoBehaviour
    {
        public static OverlookDirector Instance { get; private set; }
        public Transform[] overlooks;
        public float switchDistance = 70f;

        CourierVehicle m_Car;
        Transform m_Current;
        bool m_Switching;

        void Awake() => Instance = this;
        void OnDestroy() { if (Instance == this) Instance = null; }

        public bool Active => m_Car != null;

        public void Begin(CourierVehicle car)
        {
            m_Car = car;
            m_Current = Nearest(car.Position);
            if (m_Current != null) PlayerRigs.Instance.TeleportTo(m_Current.position, YawTowards(m_Current.position, car.Position));
            DialogueDirector.Instance?.Play("g.remote_drive");
        }

        public void End()
        {
            m_Car = null;
            m_Current = null;
        }

        Transform Nearest(Vector3 p)
        {
            Transform best = null;
            float bestD = float.MaxValue;
            foreach (var o in overlooks)
            {
                if (o == null) continue;
                float d = Vector3.Distance(new Vector3(o.position.x, 0f, o.position.z), new Vector3(p.x, 0f, p.z));
                if (d < bestD) { bestD = d; best = o; }
            }
            return best;
        }

        static float YawTowards(Vector3 from, Vector3 to)
        {
            Vector3 d = to - from;
            return Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
        }

        void Update()
        {
            if (m_Car == null || m_Current == null || m_Switching) return;
            float d = Vector3.Distance(new Vector3(m_Current.position.x, 0f, m_Current.position.z), new Vector3(m_Car.Position.x, 0f, m_Car.Position.z));
            if (d < switchDistance) return;
            var next = Nearest(m_Car.Position);
            if (next != null && next != m_Current) StartCoroutine(SwitchTo(next));
        }

        IEnumerator SwitchTo(Transform next)
        {
            m_Switching = true;
            yield return ScreenFader.Instance.FadeOut(0.2f);
            m_Current = next;
            PlayerRigs.Instance.TeleportTo(next.position, YawTowards(next.position, m_Car.Position));
            yield return ScreenFader.Instance.FadeIn(0.3f);
            m_Switching = false;
        }
    }
}
