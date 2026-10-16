using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    public enum AircraftState { Dark, Powered, Boarding, Ready, Taxi, TakeoffRoll, Climb, Departed }

    /// <summary>
    /// The last flight. It is not a decoration: it only powers up with substation power, boards
    /// when the convoy has arrived, and taxis only after the departure lever is pulled, which in
    /// turn requires power, lit beacons and passengers. Not manually flyable (stretch goal).
    /// </summary>
    public sealed class AircraftSequence : MonoBehaviour
    {
        public static AircraftSequence Instance { get; private set; }

        public Transform[] props;
        public Transform door;
        public Light navLeft, navRight, beacon, landing;
        public Renderer[] cabinWindows;
        public List<Transform> passengers = new List<Transform>();

        public AircraftState State { get; private set; } = AircraftState.Dark;
        public bool RequireBeacons = true;
        public bool RequireConvoy = true;

        CityState m_City;
        readonly List<Vector3> m_Path = new List<Vector3>();
        int m_PathIndex;
        float m_Speed;
        float m_PropSpeed;
        float m_DoorAngle;
        Quaternion m_DoorBase;
        bool m_HasDoorBase;
        float m_BoardTimer;
        float m_StateTime;
        float m_Pitch, m_Bank;
        bool m_Cinematic;
        Transform m_CinePoint;
        AudioSource m_Engine;
        bool? m_LightsPowered;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        Anchor m_Park, m_Taxi1, m_Taxi2, m_RunwayStart, m_Liftoff, m_Exit;

        void Awake()
        {
            Instance = this;
            m_Block = new MaterialPropertyBlock();
        }

        void Start()
        {
            if (AudioDirector.Instance != null) m_Engine = AudioDirector.Instance.CreateLoop("plane_idle_loop", transform, 10f);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void Bind(CityState city, CityLayout layout)
        {
            m_City = city;
            m_Park = layout.GetAnchor("plane.park");
            m_Taxi1 = layout.GetAnchor("plane.taxi.1");
            m_Taxi2 = layout.GetAnchor("plane.taxi.2");
            m_RunwayStart = layout.GetAnchor("plane.runway.start");
            m_Liftoff = layout.GetAnchor("plane.liftoff");
            m_Exit = layout.GetAnchor("plane.exit");
        }

        bool Powered => m_City != null && m_City.GetFlag(Flags.SubstationPowered);
        bool BeaconsLit => !RequireBeacons || (BeaconSystem.Instance != null && BeaconSystem.Instance.AllLit);
        bool ConvoyArrived => !RequireConvoy || (m_City != null && m_City.GetFlag(Flags.ConvoyArrived));
        bool Boarded => State >= AircraftState.Ready || (State == AircraftState.Boarding && m_BoardTimer <= 0f) || !RequireConvoy;

        public bool ConditionsMet => Powered && BeaconsLit && ConvoyArrived && State == AircraftState.Ready;

        public string MissingConditions()
        {
            var parts = new List<string>();
            if (!Powered) parts.Add("the airfield has no power");
            if (!BeaconsLit) parts.Add("the runway beacons are dark");
            if (!ConvoyArrived) parts.Add("the passengers have not arrived");
            else if (State == AircraftState.Boarding) parts.Add("passengers are still boarding");
            return string.Join(", ", parts);
        }

        /// <summary>
        /// Laptop only: a side-on shot from over the water north of the runway that follows the roll
        /// and climb. VR never takes the camera away from the player.
        /// </summary>
        void BeginDesktopCinematic()
        {
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            if (rigs == null || input == null || rigs.Mode != PlayMode.Desktop || rigs.IsDriving || input.Context != InputContext.OnFoot) return;
            if (m_CinePoint == null) m_CinePoint = new GameObject("Takeoff Camera Point").transform;
            m_CinePoint.position = new Vector3(104f, 6.5f, 156f);
            rigs.desktop.SetOverlook(m_CinePoint);
            rigs.desktop.chaseTarget = transform;
            rigs.desktop.SetView(DesktopView.Overlook);
            input.SetContext(InputContext.Cutscene);
            m_Cinematic = true;
        }

        void EndDesktopCinematic()
        {
            if (!m_Cinematic) return;
            m_Cinematic = false;
            var rigs = PlayerRigs.Instance;
            var input = InputRouter.Instance;
            if (rigs == null || rigs.desktop == null) return;
            rigs.desktop.SetView(DesktopView.FirstPerson);
            if (input != null && input.Context == InputContext.Cutscene) input.SetContext(InputContext.OnFoot);
            rigs.desktop.UpdateCursor();
        }

        public void ResetToPark()
        {
            EndDesktopCinematic();
            transform.SetPositionAndRotation(m_Park.Position, m_Park.Rotation);
            m_Pitch = m_Bank = 0f;
            m_Speed = 0f;
            m_PropSpeed = 0f;
            m_DoorAngle = 0f;
            m_BoardTimer = 0f;
            gameObject.SetActive(true);
            SetState(Powered ? AircraftState.Powered : AircraftState.Dark);
            if (m_Engine != null) m_Engine.Stop();
            foreach (var p in passengers) if (p != null) p.gameObject.SetActive(false);
            ApplyLights();
        }

        void SetState(AircraftState s)
        {
            State = s;
            m_StateTime = 0f;
            if (s == AircraftState.Taxi)
            {
                m_Path.Clear();
                m_Path.Add(m_Taxi1.Position);
                m_Path.Add(m_Taxi2.Position);
                m_Path.Add(m_RunwayStart.Position);
                m_PathIndex = 0;
                AudioDirector.Instance?.PlayAt("plane_spoolup", transform.position, 1f, 1f, 15f);
                AudioDirector.Instance?.SetMusic("music_finale", 1.5f);
            }
            if (s == AircraftState.TakeoffRoll) { AudioDirector.Instance?.PlayAt("plane_takeoff", transform.position, 1f, 1f, 25f); BeginDesktopCinematic(); }
            if (s == AircraftState.Departed) { Debug.Log("[SKYFOLD] The last flight has departed."); EndDesktopCinematic(); }
        }

        void Update()
        {
            float dt = Time.deltaTime;
            m_StateTime += dt;
            switch (State)
            {
                case AircraftState.Dark:
                    if (Powered) SetState(AircraftState.Powered);
                    break;
                case AircraftState.Powered:
                    if (!RequireConvoy) { SetState(AircraftState.Ready); break; }
                    if (ConvoyArrived) { SetState(AircraftState.Boarding); m_BoardTimer = 5f; BeginBoarding(); }
                    break;
                case AircraftState.Boarding:
                    m_BoardTimer -= dt;
                    UpdatePassengers();
                    if (m_BoardTimer <= 0f) SetState(AircraftState.Ready);
                    break;
                case AircraftState.Ready:
                    if (m_City != null && m_City.GetFlag(Flags.DepartureCleared)) SetState(AircraftState.Taxi);
                    break;
                case AircraftState.Taxi:
                    Taxi(dt);
                    break;
                case AircraftState.TakeoffRoll:
                    Roll(dt);
                    break;
                case AircraftState.Climb:
                    Climb(dt);
                    break;
            }

            float doorTarget = State == AircraftState.Boarding ? 1f : 0f;
            m_DoorAngle = Mathf.MoveTowards(m_DoorAngle, doorTarget, dt * 0.8f);
            if (door != null)
            {
                if (!m_HasDoorBase) { m_DoorBase = door.localRotation; m_HasDoorBase = true; }
                door.localRotation = m_DoorBase * Quaternion.Euler(0f, 0f, Mathf.SmoothStep(0f, 1f, m_DoorAngle) * 125f);
            }

            float propTarget = State switch
            {
                AircraftState.Dark => 0f,
                AircraftState.Powered => 0f,
                AircraftState.Boarding => 0f,
                AircraftState.Ready => 600f,
                AircraftState.Taxi => 1500f,
                _ => 2600f
            };
            m_PropSpeed = Mathf.MoveTowards(m_PropSpeed, propTarget, dt * 900f);
            if (props != null) foreach (var p in props) if (p != null) p.Rotate(Vector3.forward, m_PropSpeed * dt, Space.Self);
            UpdateEngineAudio();
            ApplyLights();
        }

        void BeginBoarding()
        {
            AudioDirector.Instance?.PlayAt("door_chime", transform.position, 0.8f);
            foreach (var p in passengers) if (p != null) p.gameObject.SetActive(true);
        }

        void UpdatePassengers()
        {
            // Passengers walk from the terminal kerb to the door and disappear inside.
            var stop = SceneRegistry.Get("terminal.stop");
            var doorPoint = door != null ? door.position : transform.position;
            for (int i = 0; i < passengers.Count; i++)
            {
                var p = passengers[i];
                if (p == null || stop == null) continue;
                float t = Mathf.Clamp01((5f - m_BoardTimer - i * 0.7f) / 3.2f);
                Vector3 a = stop.position + Vector3.right * (i * 0.8f);
                Vector3 b = new Vector3(doorPoint.x, 0.05f, doorPoint.z);
                p.position = Vector3.Lerp(a, b, t);
                Vector3 dir = b - a; dir.y = 0f;
                if (dir.sqrMagnitude > 0.01f) p.rotation = Quaternion.LookRotation(dir);
                p.gameObject.SetActive(t < 0.98f);
            }
        }

        void Taxi(float dt)
        {
            if (m_PathIndex >= m_Path.Count) { SetState(AircraftState.TakeoffRoll); return; }
            Vector3 target = m_Path[m_PathIndex];
            Vector3 pos = transform.position;
            Vector3 to = target - pos; to.y = 0f;
            if (to.magnitude < 3.5f) { m_PathIndex++; return; }
            // Slow right down for sharp turns so the turn circle is always tighter than the waypoint
            // radius (otherwise it can orbit a waypoint forever), then roll on at taxi speed.
            float error = Vector3.Angle(transform.forward, to);
            float want = error > 25f ? 2f : Mathf.Lerp(6.5f, 3f, error / 25f);
            m_Speed = Mathf.MoveTowards(m_Speed, want, dt * 3f);
            transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(to.normalized), 60f * dt);
            transform.position += transform.forward * m_Speed * dt;
        }

        void Roll(float dt)
        {
            m_Speed = Mathf.MoveTowards(m_Speed, 42f, dt * 7.5f);
            Quaternion want = m_RunwayStart.Rotation;
            transform.rotation = Quaternion.RotateTowards(transform.rotation, want, 30f * dt);
            transform.position += transform.forward * m_Speed * dt;
            if (transform.position.x >= m_Liftoff.Position.x) SetState(AircraftState.Climb);
        }

        void Climb(float dt)
        {
            m_Speed = Mathf.MoveTowards(m_Speed, 55f, dt * 4f);
            m_Pitch = Mathf.MoveTowards(m_Pitch, 11f, dt * 6f);
            Vector3 to = m_Exit.Position - transform.position;
            float yawTo = Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg;
            float yaw = Mathf.MoveTowardsAngle(transform.eulerAngles.y, yawTo, 9f * dt);
            float yawDelta = Mathf.DeltaAngle(transform.eulerAngles.y, yawTo);
            m_Bank = Mathf.MoveTowards(m_Bank, Mathf.Clamp(-yawDelta * 0.6f, -18f, 18f), dt * 8f);
            transform.rotation = Quaternion.Euler(-m_Pitch, yaw, m_Bank);
            transform.position += transform.forward * m_Speed * dt;
            if (m_StateTime > 20f || to.magnitude < 30f) SetState(AircraftState.Departed);
        }

        void UpdateEngineAudio()
        {
            if (m_Engine == null || AudioDirector.Instance == null) return;
            bool on = m_PropSpeed > 10f && !(GameRoot.Instance != null && GameRoot.Instance.IsPaused);
            if (on && !m_Engine.isPlaying && m_Engine.clip != null) m_Engine.Play();
            if (!on && m_Engine.isPlaying) m_Engine.Stop();
            float k = m_PropSpeed / 2600f;
            m_Engine.pitch = Mathf.Lerp(0.6f, 1.5f, k);
            m_Engine.volume = AudioDirector.Instance.LoopGain("plane_idle_loop") * Mathf.Lerp(0.3f, 1f, k);
            m_Engine.maxDistance = 400f;
        }

        void ApplyLights()
        {
            bool powered = State != AircraftState.Dark;
            if (navLeft != null) navLeft.enabled = powered;
            if (navRight != null) navRight.enabled = powered;
            if (beacon != null) beacon.enabled = powered && Mathf.Repeat(Time.time, 1.2f) < 0.15f;
            if (landing != null) landing.enabled = State >= AircraftState.Taxi && State != AircraftState.Departed;
            if (cabinWindows == null || m_LightsPowered == powered) return;
            m_LightsPowered = powered;
            foreach (var r in cabinWindows) Substation.SetEmissiveSlots(r, powered ? new Color(1f, 0.85f, 0.6f) * 2f : Color.black, m_Block);
        }
    }
}
