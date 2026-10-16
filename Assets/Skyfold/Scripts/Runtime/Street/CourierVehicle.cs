using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Comfort;

namespace Skyfold
{
    /// <summary>
    /// The small electric courier car. Simple, dependable arcade handling: raycast suspension,
    /// strong lateral grip, speed-scaled steering, controlled reverse. Roll and pitch are frozen
    /// so the horizon is always stable in VR; the seat only ever yaws.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public sealed class CourierVehicle : MonoBehaviour, ITunnelingVignetteProvider
    {
        public static CourierVehicle Instance { get; private set; }

        [Header("Rig points")]
        public Transform seat;
        public Transform eye;
        public Transform exitLeft, exitRight;
        public Transform body;
        public Transform[] wheels = new Transform[4]; // FL, FR, RL, RR
        public Transform steeringWheel;
        public CellSocket cradle;
        public Light[] headlights;

        [Header("Handling")]
        public float maxSpeed = 12.5f;
        public float reverseMax = 3.5f;
        public float acceleration = 6.5f;
        public float brakeDecel = 14f;
        public float coastDecel = 1.6f;
        public float grip = 9f;
        public float maxSteerRate = 80f;
        public float wheelRadius = 0.32f;
        public float suspensionRest = 0.62f;
        public float springK = 17000f, damperC = 3200f;

        Rigidbody m_Rb;
        float m_Steer, m_SteerSmoothed, m_Throttle, m_Brake;
        bool m_Handbrake;
        float m_ReverseHold;
        float m_StuckTime, m_ResetHold;
        bool m_ResetLatched;
        string m_ShownHint;
        int m_GroundedWheels;
        bool m_Grounded;
        float m_WheelSpin;
        AudioSource m_Motor, m_Roll;
        readonly HashSet<Vector2Int> m_Visited = new HashSet<Vector2Int>();
        Vector2Int m_Cell;
        bool m_VignetteOn;
        bool m_ControllerHold;
        VignetteParameters m_VignetteParams;

        public bool HasDriver { get; private set; }
        public bool Remote { get; private set; }
        public bool Busy { get; private set; }
        public float Speed => m_Rb != null ? Vector3.Dot(m_Rb.linearVelocity, transform.forward) : 0f;
        public Vector2Int Cell => m_Cell;
        public Vector3 Position => transform.position;
        public VignetteParameters vignetteParameters => m_VignetteParams;

        // Read-only telemetry for diagnostics and automated QA.
        public int GroundedWheels => m_GroundedWheels;
        public float ThrottleInput => m_Throttle;
        public float BrakeInput => m_Brake;
        public float SteerInput => m_SteerSmoothed;
        /// <summary>Raised for notable physics events (bumps) when something is listening, e.g. QA.</summary>
        public static System.Action<string> DebugEvent;

        static readonly Vector3[] WheelOffsets =
        {
            new Vector3(-0.68f, 0f, 1.08f), new Vector3(0.68f, 0f, 1.08f),
            new Vector3(-0.68f, 0f, -1.02f), new Vector3(0.68f, 0f, -1.02f)
        };

        void Awake()
        {
            Instance = this;
            m_Rb = GetComponent<Rigidbody>();
            m_Rb.mass = 700f;
            m_Rb.linearDamping = 0f;
            m_Rb.angularDamping = 3f;
            m_Rb.interpolation = RigidbodyInterpolation.Interpolate;
            m_Rb.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;
            m_Rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
            m_Rb.centerOfMass = new Vector3(0f, 0.45f, 0f);
            m_VignetteParams = new VignetteParameters { apertureSize = 0.72f, featheringEffect = 0.25f, easeInTime = 0.4f, easeOutTime = 0.5f };
        }

        void Start()
        {
            var audio = AudioDirector.Instance;
            if (audio != null)
            {
                m_Motor = audio.CreateLoop("car_motor_loop", transform, 4f);
                m_Roll = audio.CreateLoop("car_roll_loop", transform, 4f);
            }
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public float DistanceTo(string target)
        {
            var t = SceneRegistry.Get(target);
            if (t == null) return float.MaxValue;
            Vector3 d = t.position - transform.position;
            d.y = 0f;
            return d.magnitude;
        }

        public bool Visited(Vector2Int c) => m_Visited.Contains(c);

        /// <summary>True once the car has driven over a bridge the player placed and reached the island.</summary>
        public bool CrossedBuiltBridge
        {
            get
            {
                var city = GameRoot.Instance != null ? GameRoot.Instance.City : null;
                if (city == null) return false;
                if (m_Cell.y < 5) return false;
                foreach (var s in city.Layout.Sockets)
                {
                    if (!s.Water) continue;
                    var p = city.GetPlacement(s.Id);
                    if (!p.IsEmpty && !p.Locked && m_Visited.Contains(s.Cell)) return true;
                }
                return false;
            }
        }

        public void ClearVisited() => m_Visited.Clear();

        // ------------------------------------------------------------------ enter / exit
        public bool CanEnter(out string reason)
        {
            reason = null;
            if (HasDriver || Busy) { reason = ""; return false; }
            if (Mathf.Abs(Speed) > 1f) { reason = "Wait for the car to stop."; return false; }
            return true;
        }

        public void RequestEnter()
        {
            if (!CanEnter(out var reason)) { if (!string.IsNullOrEmpty(reason)) HUDMessages.Toast(reason); return; }
            StartCoroutine(EnterRoutine());
        }

        IEnumerator EnterRoutine()
        {
            Busy = true;
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            bool remote = rigs.Mode == PlayMode.VR && SettingsStore.Current.driveComfort == DriveComfort.RemoteOverlook;
            AudioDirector.Instance?.PlayAt("car_enter", transform.position, 0.8f);
            yield return ScreenFader.Instance.FadeOut(0.2f);
            HasDriver = true;
            Remote = remote;
            rigs.IsDriving = true;
            if (rigs.Mode == PlayMode.VR)
            {
                if (remote) OverlookDirector.Instance?.Begin(this);
                else rigs.vr.AttachToSeat(seat, eye);
            }
            else
            {
                rigs.desktop.chaseTarget = transform;
                rigs.desktop.SetBodyEnabled(false); // the walking capsule must not block the car
                rigs.desktop.SetView(DesktopView.Chase);
            }
            input.SetContext(remote ? InputContext.RemoteDriving : InputContext.Driving);
            if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(input.Context);
            if (rigs.Mode == PlayMode.Desktop) rigs.desktop.UpdateCursor();
            AudioDirector.Instance?.PlayAt("car_start", transform.position, 0.9f);
            AudioDirector.Instance?.SetMusic("music_drive_loop");
            foreach (var l in headlights) if (l != null) l.enabled = true;
            yield return ScreenFader.Instance.FadeIn(0.3f);
            Busy = false;
        }

        public bool CanExit(out string reason)
        {
            reason = null;
            if (!HasDriver || Busy) { reason = ""; return false; }
            if (Mathf.Abs(Speed) > 0.6f) { reason = "Stop the car before climbing out."; return false; }
            if (!FindExit(out _)) { reason = "There is no room to climb out here. Move the car a little."; return false; }
            return true;
        }

        Transform m_ExitPoint;

        /// <summary>
        /// Finds a safe place to stand beside the car: the driver's door first, then the other side,
        /// then a little further out, behind and in front. Each spot needs solid ground (a raised kerb
        /// is fine) and a clear standing space above that ground.
        /// </summary>
        bool FindExit(out Transform exit)
        {
            exit = null;
            int mask = ~LayerMask.GetMask("Vehicle", "Trigger", "MiniCity", "PlayerBody", "WorldUI", "Water", "Interactable");
            Vector3 r = transform.right, f = transform.forward;
            var candidates = new List<Vector3>();
            if (exitLeft != null) candidates.Add(exitLeft.position);
            if (exitRight != null) candidates.Add(exitRight.position);
            candidates.Add(transform.position - r * 2.3f);
            candidates.Add(transform.position + r * 2.3f);
            candidates.Add(transform.position - f * 3.1f);
            candidates.Add(transform.position + f * 3.3f);
            foreach (var c in candidates)
            {
                if (!Physics.Raycast(c + Vector3.up * 1.8f, Vector3.down, out var ground, 3.5f, mask, QueryTriggerInteraction.Ignore)) continue;
                if (ground.point.y < CityLayout.WaterLevel + 0.4f || ground.normal.y < 0.7f) continue;
                Vector3 g = ground.point;
                if (Physics.CheckCapsule(g + Vector3.up * 0.32f, g + Vector3.up * 1.6f, 0.26f, mask, QueryTriggerInteraction.Ignore)) continue;
                if (m_ExitPoint == null) { m_ExitPoint = new GameObject("Exit Point").transform; m_ExitPoint.SetParent(transform, false); }
                m_ExitPoint.position = g + Vector3.up * 0.02f;
                exit = m_ExitPoint;
                return true;
            }
            Debug.Log($"[SKYFOLD] No room to climb out of the car at {transform.position}");
            return false;
        }

        public void RequestExit()
        {
            if (!CanExit(out var reason)) { if (!string.IsNullOrEmpty(reason)) HUDMessages.Toast(reason); return; }
            StartCoroutine(ExitRoutine());
        }

        IEnumerator ExitRoutine()
        {
            Busy = true;
            FindExit(out var exit);
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            yield return ScreenFader.Instance.FadeOut(0.2f);
            EndDriving(exit.position, transform.eulerAngles.y - 90f);
            yield return ScreenFader.Instance.FadeIn(0.3f);
            Busy = false;
        }

        /// <summary>Takes the player out of the car at a validated point (exit, mission reset, retry).</summary>
        public void EndDriving(Vector3 feet, float yaw)
        {
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            bool wasRemote = Remote;
            HasDriver = false;
            Remote = false;
            m_Throttle = m_Brake = m_Steer = 0f;
            if (rigs == null) return;
            rigs.IsDriving = false;
            if (rigs.Mode == PlayMode.VR)
            {
                if (wasRemote) OverlookDirector.Instance?.End();
                if (rigs.vr.IsSeated) rigs.vr.DetachFromSeat(feet, yaw);
                else rigs.vr.TeleportTo(feet, yaw);
            }
            else
            {
                rigs.desktop.TeleportTo(feet, yaw);
                rigs.desktop.SetView(DesktopView.FirstPerson);
            }
            SetVignette(false);
            if (input != null)
            {
                input.SetContext(InputContext.OnFoot);
                if (rigs.Mode == PlayMode.VR) rigs.vr.SetContext(InputContext.OnFoot);
                else rigs.desktop.UpdateCursor();
            }
            AudioDirector.Instance?.SetMusic("music_street_loop");
        }

        public void ResetTo(Vector3 position, float yaw)
        {
            if (HasDriver) EndDriving(exitLeft != null ? exitLeft.position : position + Vector3.left * 2f, yaw);
            m_Rb.linearVelocity = Vector3.zero;
            m_Rb.angularVelocity = Vector3.zero;
            m_Rb.position = position;
            m_Rb.rotation = Quaternion.Euler(0f, yaw, 0f);
            transform.SetPositionAndRotation(position, Quaternion.Euler(0f, yaw, 0f));
            m_Visited.Clear();
            m_Cell = CityLayout.CellOf(position);
            foreach (var l in headlights) if (l != null) l.enabled = false;
            Physics.SyncTransforms();
        }

        /// <summary>Respawn with the driver still aboard (fell in the water or left the map).</summary>
        public IEnumerator RespawnWithDriver(Vector3 position, float yaw, bool fromWater = true)
        {
            Busy = true;
            if (fromWater) AudioDirector.Instance?.PlayAt("splash", transform.position, 1f);
            yield return ScreenFader.Instance.FadeOut(0.25f);
            m_Rb.linearVelocity = Vector3.zero;
            m_Rb.angularVelocity = Vector3.zero;
            m_Rb.position = position + Vector3.up * 0.1f;
            m_Rb.rotation = Quaternion.Euler(0f, yaw, 0f);
            transform.SetPositionAndRotation(m_Rb.position, m_Rb.rotation);
            Physics.SyncTransforms();
            if (PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.VR && PlayerRigs.Instance.vr.IsSeated)
                PlayerRigs.Instance.vr.Recenter();
            DialogueDirector.Instance?.Play("g.car_respawn");
            AudioDirector.Instance?.PlayAt("respawn", position, 0.9f);
            yield return ScreenFader.Instance.FadeIn(0.35f);
            Busy = false;
        }

        // ------------------------------------------------------------------ per-frame
        void Update()
        {
            var input = InputRouter.Instance;
            bool driving = HasDriver && !Busy && input != null &&
                           (input.Context == InputContext.Driving || input.Context == InputContext.RemoteDriving);

            m_ControllerHold = false;
            string hint = null;
            if (driving && PlayerRigs.Instance.Mode == PlayMode.VR && XRBootstrap.Instance != null && !XRBootstrap.Instance.ControllersTracked)
            {
                // Never drive blind: hold the car still until both controllers are tracked again.
                m_ControllerHold = true;
                hint = "Controller not tracked. The car is holding still until both controllers are visible.";
            }

            if (driving && !m_ControllerHold)
            {
                m_Steer = Mathf.Clamp(input.Steer.ReadValue<float>(), -1f, 1f);
                m_Throttle = Mathf.Clamp01(input.Throttle.ReadValue<float>());
                m_Brake = Mathf.Clamp01(input.Brake.ReadValue<float>());
                m_Handbrake = input.Handbrake.IsPressed();
                if (input.Horn.WasPressedThisFrame()) AudioDirector.Instance?.PlayAt("car_horn", transform.position, 0.8f);
                if (input.Exit.WasPressedThisFrame()) RequestExit();

                // Stuck against something: suggest reversing, and offer a hold-to-reset back onto the road.
                bool pushing = m_Throttle > 0.4f || m_Brake > 0.4f;
                m_StuckTime = pushing && Mathf.Abs(Speed) < 0.4f ? m_StuckTime + Time.deltaTime : Mathf.Max(0f, m_StuckTime - Time.deltaTime * 2f);
                if (input.ResetCar.IsPressed())
                {
                    m_ResetHold += Time.deltaTime;
                    if (m_ResetHold > 0.9f && !m_ResetLatched)
                    {
                        m_ResetLatched = true;
                        m_StuckTime = 0f;
                        MissionDirector.Instance?.RequestCarReset();
                    }
                }
                else { m_ResetHold = 0f; m_ResetLatched = false; }
                if (m_StuckTime > 2.5f)
                {
                    bool vr = PlayerRigs.Instance.Mode == PlayMode.VR;
                    hint = vr ? "Stuck? Hold the left trigger to reverse, or hold X to put the car back on the road."
                              : "Stuck? Hold S to reverse, or hold R to put the car back on the road.";
                }
            }
            else
            {
                // Parked, entering, exiting or holding for tracking: the parking brake keeps it still.
                m_Steer = 0f;
                m_Throttle = 0f;
                m_Brake = 0f;
                m_Handbrake = true;
                m_StuckTime = 0f;
                m_ResetHold = 0f;
            }
            ShowHint(hint);

            m_SteerSmoothed = Mathf.MoveTowards(m_SteerSmoothed, m_Steer, Time.deltaTime * 3.2f);
            UpdateVisuals();
            UpdateAudio();
            SetVignette(HasDriver && !Remote && PlayerRigs.Instance.Mode == PlayMode.VR && SettingsStore.Current.vignette && Mathf.Abs(Speed) > 1.2f);
        }

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            m_Grounded = false;
            float grounded = 0f;
            for (int i = 0; i < 4; i++)
            {
                Vector3 origin = transform.TransformPoint(WheelOffsets[i] + Vector3.up * suspensionRest);
                if (Physics.Raycast(origin, Vector3.down, out var hit, suspensionRest + 0.35f, ~LayerMask.GetMask("Vehicle", "Trigger", "MiniCity", "PlayerBody", "WorldUI"), QueryTriggerInteraction.Ignore))
                {
                    float compression = suspensionRest - hit.distance;
                    float vel = m_Rb.GetPointVelocity(origin).y;
                    float force = springK * compression - damperC * vel;
                    if (force > 0f) m_Rb.AddForce(Vector3.up * force, ForceMode.Force);
                    grounded += 1f;
                }
            }
            m_Grounded = grounded > 0f;
            m_GroundedWheels = (int)grounded;

            Vector3 v = m_Rb.linearVelocity;
            Vector3 fwd = transform.forward;
            Vector3 right = transform.right;
            float vf = Vector3.Dot(v, fwd);
            float vr = Vector3.Dot(v, right);

            if (m_Grounded)
            {
                float a;
                if (m_Handbrake)
                {
                    // Parking brake: stop and hold, never creep or reverse.
                    a = -Mathf.Sign(vf) * Mathf.Min(brakeDecel, Mathf.Abs(vf) / dt);
                    m_ReverseHold = 0f;
                }
                else if (m_Throttle > 0.05f && vf > -0.3f)
                {
                    a = vf < maxSpeed * m_Throttle ? acceleration * m_Throttle : -coastDecel;
                    m_ReverseHold = 0f;
                }
                else if (m_Brake > 0.05f)
                {
                    if (vf > 0.25f) { a = -brakeDecel * m_Brake; m_ReverseHold = 0f; }
                    else
                    {
                        // Controlled reverse: only after holding the brake at a standstill.
                        m_ReverseHold += dt;
                        a = m_ReverseHold > 0.35f && vf > -reverseMax * m_Brake ? -acceleration * 0.45f * m_Brake : (vf < -0.05f && m_ReverseHold <= 0.35f ? brakeDecel : 0f);
                    }
                }
                else if (m_Throttle > 0.05f && vf <= -0.3f)
                {
                    a = brakeDecel * m_Throttle; // throttle while rolling backwards brakes first
                }
                else
                {
                    a = -Mathf.Sign(vf) * Mathf.Min(coastDecel, Mathf.Abs(vf) / dt);
                    m_ReverseHold = 0f;
                }
                vf += a * dt;
                if (vf > maxSpeed) vf = maxSpeed;
                if (vf < -reverseMax) vf = -reverseMax;
                vr *= Mathf.Exp(-grip * dt);
                m_Rb.linearVelocity = fwd * vf + right * vr + Vector3.up * v.y;

                float speedFactor = Mathf.Clamp01(Mathf.Abs(vf) / 2.5f) * Mathf.Lerp(1f, 0.65f, Mathf.Abs(vf) / maxSpeed);
                float yawRate = m_SteerSmoothed * maxSteerRate * speedFactor * Mathf.Sign(vf == 0f ? 1f : vf);
                m_Rb.MoveRotation(m_Rb.rotation * Quaternion.Euler(0f, yawRate * dt, 0f));
            }

            var cell = CityLayout.CellOf(transform.position);
            if (cell != m_Cell)
            {
                m_Cell = cell;
                m_Visited.Add(cell);
                MissionDirector.Instance?.OnCarEnteredCell(cell);
            }

            // Safety net: water or off the map respawns at the last driving checkpoint.
            bool lost = transform.position.y < CityLayout.WaterLevel + 0.2f ||
                        transform.position.x < -60f || transform.position.x > 260f || transform.position.z < -60f || transform.position.z > 210f;
            if (lost && !Busy) MissionDirector.Instance?.OnCarLost();
        }

        void UpdateVisuals()
        {
            float vf = Speed;
            m_WheelSpin = Mathf.Repeat(m_WheelSpin + vf / wheelRadius * Mathf.Rad2Deg * Time.deltaTime, 360f);
            if (m_WheelBase == null) CaptureRestPose();
            for (int i = 0; i < wheels.Length; i++)
            {
                if (wheels[i] == null) continue;
                float steer = i < 2 ? m_SteerSmoothed * 26f : 0f;
                // Spin about the axle (parent X), steer about the parent's up, keep the modelled rest pose.
                wheels[i].localRotation = Quaternion.Euler(0f, steer, 0f) * Quaternion.Euler(m_WheelSpin, 0f, 0f) * m_WheelBase[i];
            }
            // The column is tilted (rest rotation 35, 0, 0); the wheel turns about its own local Z.
            if (steeringWheel != null) steeringWheel.localRotation = m_SteeringBase * Quaternion.Euler(0f, 0f, -m_SteerSmoothed * 90f);
            if (body != null)
            {
                bool vr = PlayerRigs.Instance != null && PlayerRigs.Instance.Mode == PlayMode.VR && HasDriver && !Remote;
                float roll = vr ? 0f : -m_SteerSmoothed * Mathf.Clamp01(Mathf.Abs(vf) / maxSpeed) * 2.2f;
                float pitch = vr ? 0f : (m_Brake - m_Throttle) * 1.2f * Mathf.Clamp01(Mathf.Abs(vf) / 4f);
                body.localRotation = Quaternion.Slerp(body.localRotation, Quaternion.Euler(pitch, 0f, roll), 1f - Mathf.Exp(-6f * Time.deltaTime));
            }
        }

        Quaternion[] m_WheelBase;
        Quaternion m_SteeringBase = Quaternion.identity;

        void CaptureRestPose()
        {
            m_WheelBase = new Quaternion[wheels.Length];
            for (int i = 0; i < wheels.Length; i++) m_WheelBase[i] = wheels[i] != null ? wheels[i].localRotation : Quaternion.identity;
            if (steeringWheel != null) m_SteeringBase = steeringWheel.localRotation;
        }

        void UpdateAudio()
        {
            var audio = AudioDirector.Instance;
            if (audio == null) return;
            float speed01 = Mathf.Clamp01(Mathf.Abs(Speed) / maxSpeed);
            bool paused = GameRoot.Instance != null && GameRoot.Instance.IsPaused;
            if (m_Motor != null)
            {
                bool on = HasDriver && !paused;
                if (on && !m_Motor.isPlaying && m_Motor.clip != null) m_Motor.Play();
                if (!on && m_Motor.isPlaying) m_Motor.Stop();
                m_Motor.pitch = Mathf.Lerp(0.7f, 1.75f, speed01) + m_Throttle * 0.05f;
                m_Motor.volume = audio.LoopGain("car_motor_loop") * (0.35f + 0.65f * Mathf.Max(speed01, m_Throttle * 0.5f));
            }
            if (m_Roll != null)
            {
                bool on = speed01 > 0.02f && m_Grounded && !paused;
                if (on && !m_Roll.isPlaying && m_Roll.clip != null) m_Roll.Play();
                if (!on && m_Roll.isPlaying) m_Roll.Stop();
                m_Roll.volume = audio.LoopGain("car_roll_loop") * speed01;
                m_Roll.pitch = Mathf.Lerp(0.8f, 1.3f, speed01);
            }
        }

        void ShowHint(string text)
        {
            if (text == m_ShownHint) return;
            // Only clear a hint this car put up; other systems own theirs.
            if (text != null || HUDMessages.Hint == m_ShownHint) HUDMessages.SetHint(text);
            m_ShownHint = text;
        }

        void SetVignette(bool on)
        {
            if (on == m_VignetteOn) return;
            m_VignetteOn = on;
            var rigs = PlayerRigs.Instance;
            var v = rigs != null && rigs.vr != null ? rigs.vr.Vignette : null;
            if (v == null) return;
            m_VignetteParams.apertureSize = Mathf.Lerp(0.95f, 0.6f, SettingsStore.Current.vignetteStrength);
            if (on) v.BeginTunnelingVignette(this);
            else v.EndTunnelingVignette(this);
        }

        void OnCollisionEnter(Collision c)
        {
            if (DebugEvent != null && c.relativeVelocity.magnitude > 0.5f)
                DebugEvent($"bump {c.collider.name} (layer {LayerMask.LayerToName(c.collider.gameObject.layer)}) at {c.GetContact(0).point} rel {c.relativeVelocity.magnitude:0.0} m/s");
            if (c.relativeVelocity.magnitude < 3f) return;
            AudioDirector.Instance?.PlayAt("car_bump", c.GetContact(0).point, Mathf.Clamp01(c.relativeVelocity.magnitude / 10f));
            if (HasDriver) PlayerRigs.Instance?.HapticBoth(Mathf.Clamp01(c.relativeVelocity.magnitude / 12f), 0.1f);
        }
    }
}
