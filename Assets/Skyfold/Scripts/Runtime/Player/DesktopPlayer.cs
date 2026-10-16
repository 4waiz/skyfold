using UnityEngine;

namespace Skyfold
{
    public enum DesktopView { FirstPerson, Architect, Chase, Title, Overlook }

    /// <summary>
    /// Laptop play: CharacterController body with WASD and mouse look, plus camera modes for the
    /// architect plinth view, the car chase view and the title screen. Cursor lock follows context.
    /// </summary>
    public sealed class DesktopPlayer : MonoBehaviour
    {
        public Camera cam;
        public Transform head;
        public float eyeHeight = 1.62f;
        public float walkSpeed = 3.6f;
        public float slowSpeed = 1.7f;
        public float gravity = -20f;
        public float lookSensitivity = 0.085f;

        [Header("Architect view")]
        public Transform plinthFocus;
        public float archDistance = 1.35f;
        public float archMinDistance = 0.55f, archMaxDistance = 2.6f;
        public float archPitch = 48f;
        public float archYaw;

        [Header("Chase view")]
        public Transform chaseTarget;
        public float chaseDistance = 7.5f, chaseHeight = 3.2f;
        bool m_HoodView;

        [Header("Title view")]
        public Transform titleFocus;
        public float titleRadius = 3.2f, titleHeight = 1.35f, titleSpeed = 4f;

        CharacterController m_Body;
        float m_Yaw, m_Pitch, m_VerticalVel;
        DesktopView m_View = DesktopView.Title;
        Vector3 m_CamVel;
        float m_StepTimer;
        float m_TitleAngle;
        Transform m_OverlookPoint;

        public DesktopView View => m_View;
        public Transform Head => head != null ? head : transform;
        public Vector3 FeetPosition => transform.position;
        public bool MovementLocked { get; set; }

        void Awake()
        {
            m_Body = GetComponent<CharacterController>();
            if (cam == null) cam = GetComponentInChildren<Camera>(true);
            m_Yaw = transform.eulerAngles.y;
        }

        public void SetView(DesktopView view)
        {
            m_View = view;
            if (view == DesktopView.FirstPerson)
            {
                cam.transform.SetParent(head, false);
                cam.transform.localPosition = Vector3.zero;
                cam.transform.localRotation = Quaternion.identity;
            }
            else
            {
                cam.transform.SetParent(null, true);
            }
            if (view == DesktopView.Architect && plinthFocus != null)
            {
                // Face the plinth from where the player stands.
                Vector3 toPlayer = transform.position - plinthFocus.position;
                toPlayer.y = 0f;
                archYaw = toPlayer.sqrMagnitude > 0.01f ? Mathf.Atan2(toPlayer.x, toPlayer.z) * Mathf.Rad2Deg : 180f;
            }
            UpdateCursor();
        }

        public void SetOverlook(Transform point) => m_OverlookPoint = point;
        public void ToggleChaseView() => m_HoodView = !m_HoodView;

        public void UpdateCursor()
        {
            var ctx = InputRouter.Instance != null ? InputRouter.Instance.Context : InputContext.Menu;
            bool locked = (ctx == InputContext.OnFoot || ctx == InputContext.Driving || ctx == InputContext.RemoteDriving || ctx == InputContext.Cutscene) && m_View != DesktopView.Architect;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }

        public void TeleportTo(Vector3 feet, float yaw)
        {
            if (m_Body != null) m_Body.enabled = false;
            transform.position = feet;
            m_Yaw = yaw;
            m_Pitch = 0f;
            transform.rotation = Quaternion.Euler(0f, m_Yaw, 0f);
            if (m_Body != null) m_Body.enabled = true;
            m_VerticalVel = 0f;
            Physics.SyncTransforms();
        }

        /// <summary>Turns the walking capsule off while the player is in the car, so it cannot block the car.</summary>
        public void SetBodyEnabled(bool on)
        {
            if (m_Body != null) m_Body.enabled = on;
            m_VerticalVel = 0f;
        }

        public void SetPitch(float pitch)
        {
            m_Pitch = Mathf.Clamp(pitch, -80f, 80f);
            if (head != null) head.localRotation = Quaternion.Euler(m_Pitch, 0f, 0f);
        }

        public void ApplySettings(GameSettings s)
        {
            if (cam != null) cam.fieldOfView = s.fov;
        }

        void Update()
        {
            var input = InputRouter.Instance;
            if (input == null) return;
            var ctx = input.Context;
            float dt = Time.deltaTime;

            if (m_View == DesktopView.FirstPerson && (ctx == InputContext.OnFoot || ctx == InputContext.Cutscene) && !MovementLocked)
            {
                var look = input.Look.ReadValue<Vector2>() * lookSensitivity * SettingsStore.Current.mouseSensitivity;
                if (Cursor.lockState != CursorLockMode.Locked) look = Vector2.zero;
                m_Yaw += look.x;
                m_Pitch = Mathf.Clamp(m_Pitch + (SettingsStore.Current.invertY ? look.y : -look.y), -80f, 80f);
                transform.rotation = Quaternion.Euler(0f, m_Yaw, 0f);
                head.localRotation = Quaternion.Euler(m_Pitch, 0f, 0f);

                var mv = input.Move.ReadValue<Vector2>();
                float speed = input.WalkSlow.IsPressed() ? slowSpeed : walkSpeed;
                Vector3 move = (transform.right * mv.x + transform.forward * mv.y);
                if (move.sqrMagnitude > 1f) move.Normalize();
                if (m_Body.isGrounded && m_VerticalVel < 0f) m_VerticalVel = -1f;
                m_VerticalVel += gravity * dt;
                m_Body.Move((move * speed + Vector3.up * m_VerticalVel) * dt);

                if (m_Body.isGrounded && move.sqrMagnitude > 0.1f)
                {
                    m_StepTimer -= dt * speed / walkSpeed;
                    if (m_StepTimer <= 0f)
                    {
                        m_StepTimer = 0.52f;
                        AudioDirector.Instance?.PlayAt("footstep_stone", transform.position, 0.45f, Random.Range(0.92f, 1.08f));
                    }
                }
            }
            else if (m_Body != null && m_Body.enabled && ctx != InputContext.Driving && ctx != InputContext.RemoteDriving)
            {
                // Keep grounded while other views are active.
                m_VerticalVel += gravity * dt;
                m_Body.Move(Vector3.up * m_VerticalVel * dt);
                if (m_Body.isGrounded) m_VerticalVel = -1f;
            }

            if (input.Context == InputContext.Driving && input.CameraToggle.WasPressedThisFrame()) ToggleChaseView();
        }

        void LateUpdate()
        {
            var input = InputRouter.Instance;
            float dt = Time.unscaledDeltaTime;
            switch (m_View)
            {
                case DesktopView.Architect:
                    if (plinthFocus == null) break;
                    if (input != null && input.Context == InputContext.Architect)
                    {
                        var orbit = input.Orbit.ReadValue<Vector2>();
                        archYaw += orbit.x * 70f * dt;
                        archPitch = Mathf.Clamp(archPitch - orbit.y * 40f * dt, 20f, 80f);
                        if (input.OrbitDrag.IsPressed())
                        {
                            var d = input.MouseDelta.ReadValue<Vector2>() * 0.18f * SettingsStore.Current.mouseSensitivity;
                            archYaw += d.x;
                            archPitch = Mathf.Clamp(archPitch - d.y, 20f, 80f);
                        }
                        float zoom = input.Zoom.ReadValue<float>();
                        if (Mathf.Abs(zoom) > 0.01f) archDistance = Mathf.Clamp(archDistance - Mathf.Sign(zoom) * 0.12f, archMinDistance, archMaxDistance);
                    }
                    var rot = Quaternion.Euler(archPitch, archYaw + 180f, 0f);
                    Vector3 target = plinthFocus.position + rot * new Vector3(0f, 0f, -archDistance);
                    cam.transform.position = Vector3.SmoothDamp(cam.transform.position, target, ref m_CamVel, 0.12f, Mathf.Infinity, dt);
                    cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(plinthFocus.position - cam.transform.position), 1f - Mathf.Exp(-12f * dt));
                    break;

                case DesktopView.Chase:
                    if (chaseTarget == null) break;
                    if (m_HoodView)
                    {
                        Vector3 eye = chaseTarget.position + chaseTarget.up * 1.25f + chaseTarget.forward * 0.1f;
                        cam.transform.position = eye;
                        cam.transform.rotation = Quaternion.LookRotation(chaseTarget.forward, Vector3.up);
                    }
                    else
                    {
                        Vector3 fwd = Vector3.ProjectOnPlane(chaseTarget.forward, Vector3.up).normalized;
                        Vector3 desired = chaseTarget.position - fwd * chaseDistance + Vector3.up * chaseHeight;
                        // Keep the camera out of walls.
                        Vector3 pivot = chaseTarget.position + Vector3.up * 1.4f;
                        if (Physics.Linecast(pivot, desired, out var hit, ~LayerMask.GetMask("Vehicle", "PlayerBody", "Trigger", "MiniCity"), QueryTriggerInteraction.Ignore))
                            desired = hit.point + (pivot - hit.point).normalized * 0.4f;
                        cam.transform.position = Vector3.SmoothDamp(cam.transform.position, desired, ref m_CamVel, 0.18f, Mathf.Infinity, dt);
                        cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(pivot + fwd * 4f - cam.transform.position), 1f - Mathf.Exp(-8f * dt));
                    }
                    break;

                case DesktopView.Overlook:
                    if (m_OverlookPoint == null || chaseTarget == null) break;
                    cam.transform.position = Vector3.SmoothDamp(cam.transform.position, m_OverlookPoint.position, ref m_CamVel, 0.3f, Mathf.Infinity, dt);
                    cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(chaseTarget.position - cam.transform.position), 1f - Mathf.Exp(-4f * dt));
                    break;

                case DesktopView.Title:
                    if (titleFocus == null) break;
                    m_TitleAngle += titleSpeed * dt;
                    var tr = Quaternion.Euler(0f, m_TitleAngle + 160f, 0f);
                    Vector3 tp = titleFocus.position + tr * new Vector3(0f, titleHeight, -titleRadius);
                    cam.transform.position = Vector3.Lerp(cam.transform.position, tp, 1f - Mathf.Exp(-2f * dt));
                    cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(titleFocus.position + Vector3.up * 0.12f - cam.transform.position), 1f - Mathf.Exp(-3f * dt));
                    break;
            }
        }

        /// <summary>Ray from the camera through the mouse cursor (architect) or screen centre (first person).</summary>
        public Ray PointerRay()
        {
            if (m_View == DesktopView.Architect && InputRouter.Instance != null)
            {
                var p = InputRouter.Instance.Point.ReadValue<Vector2>();
                return cam.ScreenPointToRay(p);
            }
            return new Ray(cam.transform.position, cam.transform.forward);
        }
    }
}
