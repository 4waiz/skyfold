using System.Collections;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// VR comfort "Remote Drive": the player stands on a fixed elevated overlook and drives the
    /// same car remotely, so there is no artificial vehicle motion. Overlooks change only with a fade.
    /// The platforms are only shown while in use, so they never float over the city as stray discs.
    /// </summary>
    public sealed class OverlookDirector : MonoBehaviour
    {
        public static OverlookDirector Instance { get; private set; }
        public Transform[] overlooks;
        public float switchDistance = 70f;

        CourierVehicle m_Car;
        Transform m_Current;
        bool m_Switching;

        void Awake()
        {
            Instance = this;
            ShowOnly(null);
        }

        void ShowOnly(Transform shown)
        {
            if (overlooks == null) return;
            foreach (var o in overlooks) if (o != null) o.gameObject.SetActive(o == shown);
        }

        /// <summary>Shows one platform without starting Remote Drive (screenshots and the tour).</summary>
        public void Preview(string id)
        {
            Transform found = null;
            if (overlooks != null) foreach (var o in overlooks) if (o != null && o.name.EndsWith(id)) found = o;
            ShowOnly(found);
        }
        void OnDestroy() { if (Instance == this) Instance = null; }

        public bool Active => m_Car != null;

        public void Begin(CourierVehicle car)
        {
            m_Car = car;
            m_Current = Nearest(car.Position);
            ShowOnly(m_Current);
            if (m_Current != null) PlayerRigs.Instance.TeleportTo(m_Current.position, YawTowards(m_Current.position, car.Position));
            DialogueDirector.Instance?.Play("g.remote_drive");
        }

        public void End()
        {
            m_Car = null;
            m_Current = null;
            ShowOnly(null);
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
            if (m_Car == null)
            {
                // Remote Drive ended during the fade: just fade back in.
                yield return ScreenFader.Instance.FadeIn(0.2f);
                m_Switching = false;
                yield break;
            }
            m_Current = next;
            ShowOnly(next);
            PlayerRigs.Instance.TeleportTo(next.position, YawTowards(next.position, m_Car.Position));
            yield return ScreenFader.Instance.FadeIn(0.3f);
            m_Switching = false;
        }
    }
}
