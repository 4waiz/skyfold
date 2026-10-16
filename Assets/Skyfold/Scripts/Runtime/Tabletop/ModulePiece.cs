using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold
{
    public enum PieceState { InTray, Held, Placed, Moving }

    /// <summary>
    /// A grabbable road/bridge module on the plinth (about 10 cm). The rigidbody root stays at
    /// scale 1; only the visual child is scaled to the miniature. Released pieces never fall:
    /// they snap into a socket or glide back to their tray slot, so nothing is ever lost.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public sealed class ModulePiece : MonoBehaviour
    {
        public string pieceId;
        public ModuleType type;
        public Transform visual;
        public Transform ghost;
        public Renderer[] ghostRenderers;
        public Transform homeSlot;

        public PieceState State { get; private set; } = PieceState.InTray;
        public string SocketId { get; set; }
        public XRGrabInteractable Grab { get; private set; }
        public bool DesktopHeld { get; private set; }

        Vector3 m_MoveFromPos, m_MoveToPos;
        Quaternion m_MoveFromRot, m_MoveToRot;
        float m_MoveT = 1f, m_MoveDuration = 0.3f;
        PieceState m_AfterMove;
        int m_DesktopQuarter;
        static readonly int ColorId = Shader.PropertyToID("_BaseColor");
        MaterialPropertyBlock m_Block;

        void Awake()
        {
            Grab = GetComponent<XRGrabInteractable>();
            var rb = GetComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            m_Block = new MaterialPropertyBlock();
            if (Grab != null)
            {
                Grab.selectEntered.AddListener(OnGrabbed);
                Grab.selectExited.AddListener(OnReleased);
            }
            HideGhost();
        }

        void OnDestroy()
        {
            if (Grab != null)
            {
                Grab.selectEntered.RemoveListener(OnGrabbed);
                Grab.selectExited.RemoveListener(OnReleased);
            }
        }

        void OnGrabbed(SelectEnterEventArgs args)
        {
            var controller = TabletopController.Instance;
            if (controller == null || !controller.BeginHold(this))
            {
                // Vetoed (e.g. a vehicle is on this module): let go immediately.
                if (Grab.interactionManager != null) Grab.interactionManager.CancelInteractableSelection((IXRSelectInteractable)Grab);
                return;
            }
            State = PieceState.Held;
            m_MoveT = 1f;
        }

        void OnReleased(SelectExitEventArgs args)
        {
            if (State != PieceState.Held) return;
            TabletopController.Instance?.Release(this);
        }

        // ------------------------------------------------------------------ desktop holding
        public void BeginDesktopHold()
        {
            DesktopHeld = true;
            State = PieceState.Held;
            m_MoveT = 1f;
            m_DesktopQuarter = DirUtil.QuarterTurnsFromYaw(MiniCity.Instance != null ? MiniCity.Instance.YawInCity(transform) : transform.eulerAngles.y);
        }

        public void DesktopRotate()
        {
            m_DesktopQuarter = (m_DesktopQuarter + 1) & 3;
            AudioDirector.Instance?.PlayAt("piece_rotate", transform.position, 0.7f);
        }

        public void DesktopFollow(Vector3 target)
        {
            transform.position = Vector3.Lerp(transform.position, target, 1f - Mathf.Exp(-18f * Time.unscaledDeltaTime));
            var mini = MiniCity.Instance;
            Quaternion targetRot = mini != null ? mini.CityToWorldRotation(Quaternion.Euler(0f, m_DesktopQuarter * 90f, 0f)) : Quaternion.Euler(0f, m_DesktopQuarter * 90f, 0f);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, 1f - Mathf.Exp(-16f * Time.unscaledDeltaTime));
        }

        public void EndDesktopHold() => DesktopHeld = false;

        public int CurrentQuarter
        {
            get
            {
                if (DesktopHeld) return m_DesktopQuarter;
                var mini = MiniCity.Instance;
                return DirUtil.QuarterTurnsFromYaw(mini != null ? mini.YawInCity(transform) : transform.eulerAngles.y);
            }
        }

        // ------------------------------------------------------------------ motion
        public void MoveTo(Vector3 pos, Quaternion rot, PieceState after, float duration = 0.28f)
        {
            m_MoveFromPos = transform.position;
            m_MoveFromRot = transform.rotation;
            m_MoveToPos = pos;
            m_MoveToRot = rot;
            m_MoveT = 0f;
            m_MoveDuration = Mathf.Max(0.05f, duration);
            m_AfterMove = after;
            State = PieceState.Moving;
        }

        public void SetImmediate(Vector3 pos, Quaternion rot, PieceState state)
        {
            transform.SetPositionAndRotation(pos, rot);
            m_MoveT = 1f;
            State = state;
        }

        void Update()
        {
            if (m_MoveT < 1f)
            {
                m_MoveT = Mathf.Min(1f, m_MoveT + Time.unscaledDeltaTime / m_MoveDuration);
                float e = 1f - Mathf.Pow(1f - m_MoveT, 3f);
                // A small arc makes returns read as "put back", not teleport.
                Vector3 p = Vector3.Lerp(m_MoveFromPos, m_MoveToPos, e) + Vector3.up * Mathf.Sin(e * Mathf.PI) * 0.05f;
                transform.SetPositionAndRotation(p, Quaternion.Slerp(m_MoveFromRot, m_MoveToRot, e));
                if (m_MoveT >= 1f) State = m_AfterMove;
            }
        }

        // ------------------------------------------------------------------ ghost preview
        public void ShowGhost(Vector3 pos, Quaternion rot, bool ok)
        {
            if (ghost == null) return;
            if (!ghost.gameObject.activeSelf) ghost.gameObject.SetActive(true);
            ghost.SetPositionAndRotation(pos, rot);
            Color c = ok ? new Color(0.21f, 0.88f, 0.82f, 0.45f) : new Color(0.95f, 0.44f, 0.29f, 0.45f);
            if (ghostRenderers != null)
                foreach (var r in ghostRenderers)
                {
                    if (r == null) continue;
                    r.GetPropertyBlock(m_Block);
                    m_Block.SetColor(ColorId, c);
                    r.SetPropertyBlock(m_Block);
                }
        }

        public void HideGhost()
        {
            if (ghost != null && ghost.gameObject.activeSelf) ghost.gameObject.SetActive(false);
        }

        public void SetGrabbable(bool on)
        {
            if (Grab != null) Grab.enabled = on;
        }
    }
}
