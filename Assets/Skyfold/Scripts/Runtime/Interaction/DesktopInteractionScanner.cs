using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Desktop "look and press E" targeting from the first-person camera.</summary>
    public sealed class DesktopInteractionScanner : MonoBehaviour
    {
        public DesktopPlayer player;
        public float maxDistance = 3.2f;
        public LayerMask mask = ~0;

        public WorldInteractable Current { get; private set; }

        void Update()
        {
            var input = InputRouter.Instance;
            WorldInteractable found = null;
            if (input != null && input.Mode == PlayMode.Desktop && input.Context == InputContext.OnFoot && player != null && player.View == DesktopView.FirstPerson)
            {
                var ray = player.PointerRay();
                if (Physics.SphereCast(ray, 0.12f, out var hit, maxDistance, mask, QueryTriggerInteraction.Collide))
                {
                    var wi = hit.collider.GetComponentInParent<WorldInteractable>();
                    if (wi != null && hit.distance <= wi.desktopRange) found = wi;
                }
                if (found == null)
                {
                    // Generous fallback: nearest interactable roughly in view and close.
                    float best = 2.2f;
                    foreach (var wi in s_All)
                    {
                        if (wi == null || !wi.isActiveAndEnabled) continue;
                        Vector3 to = wi.transform.position - ray.origin;
                        float d = to.magnitude;
                        if (d > best || d > wi.desktopRange) continue;
                        if (Vector3.Angle(ray.direction, to) > 28f) continue;
                        best = d;
                        found = wi;
                    }
                }
            }

            if (found != Current)
            {
                if (Current != null) Current.SetHighlighted(false);
                Current = found;
                if (Current != null) Current.SetHighlighted(true);
            }

            if (Current != null && input != null && input.Interact.WasPressedThisFrame())
            {
                if (Current.CanInteract(InteractorKind.Desktop)) Current.Interact(InteractorKind.Desktop);
                else if (!string.IsNullOrEmpty(Current.BlockedReason)) HUDMessages.Toast(Current.BlockedReason);
            }
        }

        static readonly List<WorldInteractable> s_All = new List<WorldInteractable>();
        public static void Register(WorldInteractable wi) { if (!s_All.Contains(wi)) s_All.Add(wi); }
        public static void Unregister(WorldInteractable wi) => s_All.Remove(wi);
    }
}
