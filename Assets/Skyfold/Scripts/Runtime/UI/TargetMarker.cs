using UnityEngine;

namespace Skyfold
{
    /// <summary>A restrained world-space marker floating above the current objective target in the street.</summary>
    public sealed class TargetMarker : MonoBehaviour
    {
        public Transform visual;
        public float height = 2.6f;

        void LateUpdate()
        {
            var md = MissionDirector.Instance;
            var fold = FoldController.Instance;
            var o = md != null ? md.CurrentObjective : null;
            var target = o != null ? SceneRegistry.Get(o.GuideTarget) : null;
            bool show = target != null && fold != null && fold.InStreet && GameRoot.Instance != null && GameRoot.Instance.IsPlaying &&
                        md.State == MissionState.Active && SettingsStore.Current.guidance != Guidance.Off;
            if (visual != null && visual.gameObject.activeSelf != show) visual.gameObject.SetActive(show);
            if (!show) return;
            float bob = Mathf.Sin(Time.time * 2.2f) * 0.18f;
            transform.position = target.position + Vector3.up * (height + bob);
            var cam = PlayerRigs.Instance != null ? PlayerRigs.Instance.ActiveCamera : null;
            if (cam != null)
            {
                Vector3 d = transform.position - cam.transform.position;
                d.y = 0f;
                if (d.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(d);
                float dist = Vector3.Distance(cam.transform.position, transform.position);
                transform.localScale = Vector3.one * Mathf.Clamp(dist * 0.06f, 0.6f, 4f);
            }
        }
    }
}
