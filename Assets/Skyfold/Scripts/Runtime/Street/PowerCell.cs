using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold
{
    public enum CellLocation { Dock, Held, CarCradle, Substation, Loose }

    /// <summary>
    /// The power cell. VR: grab it (grip) and let go near a socket. Desktop: E to pick up, E at a
    /// socket to insert. If it ever falls into the water or off the map it returns to the dock.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public sealed class PowerCell : WorldInteractable
    {
        public static PowerCell Instance { get; private set; }

        public CellSocket[] sockets;
        public CellSocket dock;
        public Renderer core;
        public float snapRadius = 0.45f;

        Rigidbody m_Rb;
        XRGrabInteractable m_Grab;
        CellSocket m_Socket;
        Transform m_DesktopHold;
        float m_LostTimer;
        Rigidbody m_IgnoredHost; // vehicle whose colliders this cell currently ignores
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        public CellLocation Location { get; private set; } = CellLocation.Dock;
        public CellSocket Socket => m_Socket;
        public bool HeldOnDesktop => m_DesktopHold != null;

        protected override void Awake()
        {
            base.Awake();
            Instance = this;
            m_Rb = GetComponent<Rigidbody>();
            m_Grab = GetComponent<XRGrabInteractable>();
            m_Block = new MaterialPropertyBlock();
            if (m_Grab != null)
            {
                m_Grab.selectEntered.AddListener(OnGrab);
                m_Grab.selectExited.AddListener(OnRelease);
            }
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            if (Instance == this) Instance = null;
            if (m_Grab != null)
            {
                m_Grab.selectEntered.RemoveListener(OnGrab);
                m_Grab.selectExited.RemoveListener(OnRelease);
            }
        }

        // ------------------------------------------------------------------ desktop
        public override bool CanInteract(InteractorKind who) =>
            base.CanInteract(who) && who == InteractorKind.Desktop && m_DesktopHold == null &&
            (m_Socket == null || m_Socket.allowRemove);

        public override string Prompt => "Pick up the power cell";

        public override void Interact(InteractorKind who)
        {
            var rigs = PlayerRigs.Instance;
            if (rigs == null || rigs.desktop == null) return;
            var hold = rigs.desktop.cam.transform.Find("CarryPoint");
            if (hold == null)
            {
                hold = new GameObject("CarryPoint").transform;
                hold.SetParent(rigs.desktop.cam.transform, false);
                hold.localPosition = new Vector3(0.32f, -0.32f, 0.75f);
            }
            TakeFromSocket();
            m_DesktopHold = hold;
            SetPhysics(false);
            transform.SetParent(hold, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.Euler(0f, 0f, -12f);
            Location = CellLocation.Held;
            AudioDirector.Instance?.PlayAt("cell_pickup", transform.position, 0.8f);
        }

        // ------------------------------------------------------------------ VR
        void OnGrab(SelectEnterEventArgs args)
        {
            if (m_Socket != null && !m_Socket.allowRemove)
            {
                m_Grab.interactionManager?.CancelInteractableSelection((IXRSelectInteractable)m_Grab);
                return;
            }
            TakeFromSocket();
            Location = CellLocation.Held;
            AudioDirector.Instance?.PlayAt("cell_pickup", transform.position, 0.8f);
        }

        void OnRelease(SelectExitEventArgs args)
        {
            if (Location != CellLocation.Held) return;
            var s = NearestSocket(transform.position);
            if (s != null) InsertInto(s);
            else { Location = CellLocation.Loose; SetPhysics(true); }
        }

        CellSocket NearestSocket(Vector3 p)
        {
            CellSocket best = null;
            float bestD = snapRadius;
            foreach (var s in sockets)
            {
                if (s == null || !s.Accepts) continue;
                float d = Vector3.Distance(s.attach.position, p);
                if (d < bestD) { bestD = d; best = s; }
            }
            return best;
        }

        // ------------------------------------------------------------------ sockets
        public void InsertInto(CellSocket s)
        {
            if (s == null) return;
            m_DesktopHold = null;
            SetPhysics(false);
            transform.SetParent(s.attach, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            m_Socket = s;
            Location = s.location;
            IgnoreHost(s);
            s.OnInserted(this);
            AudioDirector.Instance?.PlayAt("cell_insert", transform.position, 1f);
            PlayerRigs.Instance?.HapticBoth(0.5f, 0.1f);
        }

        void TakeFromSocket()
        {
            if (m_Socket == null) return;
            var s = m_Socket;
            m_Socket = null;
            transform.SetParent(null, true);
            s.OnRemoved(this);
        }

        public void DropAtFeet()
        {
            TakeFromSocket();
            m_DesktopHold = null;
            if (m_Grab != null && m_Grab.isSelected) m_Grab.interactionManager?.CancelInteractableSelection((IXRSelectInteractable)m_Grab);
            transform.SetParent(null, true);
            var rigs = PlayerRigs.Instance;
            if (rigs != null) transform.position = rigs.FeetPosition + rigs.Forward * 0.6f + Vector3.up * 0.4f;
            Location = CellLocation.Loose;
            SetPhysics(true);
        }

        public void ResetToDock()
        {
            if (m_Grab != null && m_Grab.isSelected) m_Grab.interactionManager?.CancelInteractableSelection((IXRSelectInteractable)m_Grab);
            m_DesktopHold = null;
            if (m_Socket != null) TakeFromSocket();
            InsertSilently(dock);
        }

        public void InsertSilently(CellSocket s)
        {
            if (s == null) return;
            if (m_Socket != null && m_Socket != s) TakeFromSocket();
            m_DesktopHold = null;
            SetPhysics(false);
            transform.SetParent(s.attach, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            m_Socket = s;
            Location = s.location;
            IgnoreHost(s);
            s.OnInserted(this, silent: true);
        }

        /// <summary>
        /// A cell socketed in a moving body (the car's cradle) sits inside that body's collider. Without
        /// this the physics engine keeps pushing the car out of its own cargo and the car cannot move.
        /// </summary>
        void IgnoreHost(CellSocket s)
        {
            var host = s != null ? s.GetComponentInParent<Rigidbody>() : null;
            if (host == null || host == m_Rb) return;
            if (m_IgnoredHost != null && m_IgnoredHost != host) SetHostCollisions(m_IgnoredHost, true);
            SetHostCollisions(host, false);
            m_IgnoredHost = host;
        }

        void SetHostCollisions(Rigidbody host, bool collide)
        {
            var mine = GetComponentsInChildren<Collider>(true);
            foreach (var hc in host.GetComponentsInChildren<Collider>(true))
            {
                if (hc.transform.IsChildOf(transform)) continue;
                foreach (var c in mine) Physics.IgnoreCollision(c, hc, !collide);
            }
        }

        void SetPhysics(bool dynamic)
        {
            m_Rb.isKinematic = !dynamic;
            m_Rb.useGravity = dynamic;
            if (dynamic) { m_Rb.linearVelocity = Vector3.zero; m_Rb.angularVelocity = Vector3.zero; }
            foreach (var c in GetComponentsInChildren<Collider>()) c.enabled = m_DesktopHold == null;
        }

        void Update()
        {
            // Glow pulses gently; stronger when it is the current objective.
            if (core != null)
            {
                core.GetPropertyBlock(m_Block);
                float pulse = 1.6f + 0.8f * Mathf.Sin(Time.time * 3f);
                m_Block.SetColor(EmissionId, new Color(0.21f, 0.88f, 0.82f) * pulse);
                core.SetPropertyBlock(m_Block);
            }

            // Once out of the cradle and clear of the car, collide with it again.
            if (m_IgnoredHost != null && m_Socket == null && Location != CellLocation.Held)
            {
                var hostCol = m_IgnoredHost.GetComponent<Collider>();
                if (hostCol == null || (hostCol.ClosestPoint(transform.position) - transform.position).sqrMagnitude > 0.36f)
                {
                    SetHostCollisions(m_IgnoredHost, true);
                    m_IgnoredHost = null;
                }
            }

            if (Location == CellLocation.Loose)
            {
                bool lost = transform.position.y < CityLayout.WaterLevel + 0.1f || transform.position.y < -20f ||
                            Mathf.Abs(transform.position.x - 96f) > 200f || Mathf.Abs(transform.position.z - 72f) > 200f;
                m_LostTimer = lost ? m_LostTimer + Time.deltaTime : 0f;
                if (m_LostTimer > 1.2f)
                {
                    m_LostTimer = 0f;
                    ResetToDock();
                    AudioDirector.Instance?.PlayAt("respawn", transform.position, 0.8f);
                    DialogueDirector.Instance?.Play("g.cell_respawn");
                }
            }
        }
    }
}
