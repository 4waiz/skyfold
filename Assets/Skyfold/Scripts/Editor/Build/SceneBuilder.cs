using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace Skyfold.EditorTools
{
    /// <summary>
    /// Generates the single game scene from code: lighting, sea, the full-scale city and the 1:160
    /// miniature from CityLayout, all gameplay entities, both player rigs, managers and UI, with
    /// every reference wired. Idempotent: rerun after art or code changes.
    /// </summary>
    public static partial class SceneBuilder
    {
        public const string ScenePath = "Assets/Skyfold/Scenes/Skyfold.unity";
        public const string ProfilePath = "Assets/Skyfold/Settings/SkyfoldVolume.asset";

        sealed class Ctx
        {
            public CityLayout Layout = CityLayout.NacreBay;
            public Transform Env, City, Atelier, Entities, Rigs, Systems, MiniRoot;
            public Light Sun;
            public Material Sky;
            public readonly List<FullScaleSlot> Slots = new List<FullScaleSlot>();
            public readonly List<ModulePiece> Pieces = new List<ModulePiece>();
            public readonly List<MiniatureMirror.Pair> MirrorPairs = new List<MiniatureMirror.Pair>();
            public readonly List<Light> IslandLights = new List<Light>();
            public readonly List<Renderer> IslandWindows = new List<Renderer>();
            public readonly List<FoldStation> Stations = new List<FoldStation>();
            public readonly List<Transform> Overlooks = new List<Transform>();
            public readonly List<PathVehicle> Shuttles = new List<PathVehicle>();
            public readonly List<PathVehicle> Traffic = new List<PathVehicle>();
            public readonly List<BeaconSwitch> Switches = new List<BeaconSwitch>();
            public readonly List<BeaconSystem.Group> BeaconGroups = new List<BeaconSystem.Group>();
            public Transform PlinthTop, Tray;
            public Transform[] TraySlots;
            public CourierVehicle Car;
            public PowerCell Cell;
            public CellSocket Dock, SubstationSocket;
            public Substation Substation;
            public AircraftSequence Aircraft;
            public BeaconSwitch MasterSwitch;
            public DepartureLever Lever;
            public NuriCompanion Nuri;
            public DesktopPlayer Desktop;
            public VRRigController VR;
            public MiniCity Mini;
            public LineRenderer MiniLine;
            public Transform StormFront;
            public ParticleSystem Rain;
            public Light Lightning;
            public Transform Atrium;
            public System.Random Rng = new System.Random(1607);
        }

        [MenuItem("SKYFOLD/Build/Build Scene")]
        public static void Build()
        {
            MaterialLibrary.BuildAll();
            ModelLibrary.Refresh();
            var lib = AudioSetup.Build();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var c = new Ctx();
            c.Env = Root("Environment");
            c.City = Root("City");
            c.Atelier = Root("Atelier");
            c.Entities = Root("Entities");
            c.Rigs = Root("Rigs");
            c.Systems = Root("Systems");

            BuildEnvironment(c);
            BuildCity(c, c.City, false);
            BuildAtelier(c);
            BuildEntities(c);
            BuildRigs(c);
            BuildSystems(c, lib);

            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            if (ModelLibrary.Missing.Count > 0) Debug.LogWarning("[SKYFOLD] Placeholders used for: " + string.Join(", ", ModelLibrary.Missing));
            Debug.Log("[SKYFOLD] Scene built: " + ScenePath);
        }

        public static void BatchBuild()
        {
            try { Build(); EditorApplication.Exit(0); }
            catch (System.Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }

        // ------------------------------------------------------------------ helpers
        static Transform Root(string name) => new GameObject(name).transform;

        static GameObject Child(Transform parent, string name, Vector3 localPos = default, float yaw = 0f)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
            return go;
        }

        static void SetLayer(GameObject go, string layer, bool recursive = true)
        {
            int l = LayerMask.NameToLayer(layer);
            if (l < 0) return;
            go.layer = l;
            if (recursive) foreach (Transform t in go.transform) SetLayer(t.gameObject, layer, true);
        }

        static void SetStatic(GameObject go)
        {
            GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic | StaticEditorFlags.ReflectionProbeStatic);
            foreach (Transform t in go.transform) SetStatic(t.gameObject);
        }

        static void MeshColliders(GameObject go)
        {
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null || mf.GetComponent<Collider>() != null) continue;
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
            }
        }

        static BoxCollider BoundsCollider(GameObject go, float shrink = 0.94f)
        {
            var b = ModelInspector.Bounds(go);
            var bc = go.AddComponent<BoxCollider>();
            bc.center = b.center;
            bc.size = new Vector3(b.size.x * shrink, b.size.y, b.size.z * shrink);
            return bc;
        }

        static void Teleportable(GameObject go)
        {
            var ta = go.AddComponent<UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation.TeleportationArea>();
            ta.interactionLayers = UnityEngine.XR.Interaction.Toolkit.InteractionLayerMask.GetMask("Teleport");
        }

        static Transform FindDeep(Transform root, string name) => VRRigController.FindDeep(root, name);

        static NamedTarget Named(GameObject go, string name)
        {
            var nt = go.AddComponent<NamedTarget>();
            nt.targetName = name;
            return nt;
        }

        // ------------------------------------------------------------------ environment
        static void BuildEnvironment(Ctx c)
        {
            var sunGo = Child(c.Env, "Sun");
            sunGo.transform.rotation = Quaternion.Euler(31f, 62f, 0f);
            c.Sun = sunGo.AddComponent<Light>();
            c.Sun.type = LightType.Directional;
            c.Sun.color = new Color(1f, 0.87f, 0.7f);
            c.Sun.intensity = 1.25f;
            c.Sun.shadows = LightShadows.Soft;
            c.Sun.shadowStrength = 0.82f;
            c.Sun.shadowBias = 0.05f;
            c.Sun.shadowNormalBias = 0.4f;

            var lightningGo = Child(c.Env, "Lightning");
            lightningGo.transform.rotation = Quaternion.Euler(60f, 220f, 0f);
            c.Lightning = lightningGo.AddComponent<Light>();
            c.Lightning.type = LightType.Directional;
            c.Lightning.color = new Color(0.8f, 0.85f, 1f);
            c.Lightning.shadows = LightShadows.None;
            c.Lightning.enabled = false;

            c.Sky = MaterialLibrary.Get("SKY_Sky");
            RenderSettings.skybox = c.Sky;
            RenderSettings.sun = c.Sun;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.66f, 0.74f, 0.8f);
            RenderSettings.ambientEquatorColor = new Color(0.8f, 0.72f, 0.62f);
            RenderSettings.ambientGroundColor = new Color(0.42f, 0.38f, 0.33f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.86f, 0.81f, 0.74f);
            RenderSettings.fogStartDistance = 160f;
            RenderSettings.fogEndDistance = 950f;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;

            // Sea: a subdivided plane so the gentle waves have vertices to move.
            var water = Child(c.Env, "Sea", new Vector3(96f, CityLayout.WaterLevel, 72f));
            water.AddComponent<MeshFilter>().sharedMesh = PlaneMesh("SeaPlane", 2600f, 180);
            var wr = water.AddComponent<MeshRenderer>();
            wr.sharedMaterial = MaterialLibrary.Get("SKY_Water");
            wr.shadowCastingMode = ShadowCastingMode.Off;
            SetLayer(water, "Water");

            // Post-processing: gentle tonemapping, restrained bloom for lamps and beacons.
            var volGo = Child(c.Env, "Global Volume");
            var vol = volGo.AddComponent<Volume>();
            vol.isGlobal = true;
            vol.sharedProfile = Profile();

            // Distant clouds and the storm bank that rolls in with the timer.
            var clouds = Child(c.Env, "Clouds");
            for (int i = 0; i < 14; i++)
            {
                float a = i / 14f * Mathf.PI * 2f + (float)c.Rng.NextDouble() * 0.4f;
                float r = 520f + (float)c.Rng.NextDouble() * 260f;
                var p = new Vector3(96f + Mathf.Cos(a) * r, 120f + (float)c.Rng.NextDouble() * 90f, 72f + Mathf.Sin(a) * r);
                var cl = ModelLibrary.Spawn(i % 3 == 0 ? "cloud_puff_a" : i % 3 == 1 ? "cloud_puff_b" : "cloud_puff_c", clouds.transform, p, (float)c.Rng.NextDouble() * 360f, 2.6f + (float)c.Rng.NextDouble() * 2f);
                foreach (var rr in cl.GetComponentsInChildren<Renderer>()) rr.shadowCastingMode = ShadowCastingMode.Off;
            }
            c.StormFront = Child(c.Env, "Storm Front", new Vector3(520f, 0f, 300f)).transform;
            for (int i = 0; i < 9; i++)
            {
                var p = new Vector3(-180f + i * 45f, 90f + (i % 3) * 25f, (i % 2) * 60f);
                var sc = ModelLibrary.Spawn("storm_cloud", c.StormFront, p, i * 37f, 4f + (i % 3));
                foreach (var rr in sc.GetComponentsInChildren<Renderer>()) rr.shadowCastingMode = ShadowCastingMode.Off;
            }

            // Rain (only near the end of a storm timer); follows the active camera.
            var rainGo = Child(c.Env, "Rain");
            rainGo.AddComponent<FollowActiveCamera>().offset = new Vector3(0f, 12f, 0f);
            c.Rain = rainGo.AddComponent<ParticleSystem>();
            var main = c.Rain.main;
            main.startLifetime = 1.1f;
            main.startSpeed = 22f;
            main.startSize = 0.05f;
            main.maxParticles = 3000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.playOnAwake = false;
            var shape = c.Rain.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(40f, 1f, 40f);
            shape.rotation = new Vector3(90f, 0f, 0f);
            var em = c.Rain.emission;
            em.rateOverTime = 0f;
            var psr = rainGo.GetComponent<ParticleSystemRenderer>();
            psr.renderMode = ParticleSystemRenderMode.Stretch;
            psr.lengthScale = 6f;
            psr.sharedMaterial = MaterialLibrary.Get("SKY_Rain");
        }

        static Mesh PlaneMesh(string name, float size, int segments)
        {
            string path = PlaceholderMeshes.Folder + "/" + name + ".asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null) return existing;
            var m = new Mesh { name = name, indexFormat = IndexFormat.UInt32 };
            int n = segments + 1;
            var v = new Vector3[n * n];
            var uv = new Vector2[n * n];
            var cols = new Color32[n * n];
            for (int z = 0; z < n; z++)
                for (int x = 0; x < n; x++)
                {
                    // Denser rings near the city: quadratic spacing from the centre.
                    float fx = (x / (float)segments) * 2f - 1f, fz = (z / (float)segments) * 2f - 1f;
                    fx = Mathf.Sign(fx) * fx * fx;
                    fz = Mathf.Sign(fz) * fz * fz;
                    v[z * n + x] = new Vector3(fx * size * 0.5f, 0f, fz * size * 0.5f);
                    uv[z * n + x] = new Vector2(x / (float)segments, z / (float)segments);
                    cols[z * n + x] = new Color32(255, 255, 255, 255);
                }
            var tris = new int[segments * segments * 6];
            int t = 0;
            for (int z = 0; z < segments; z++)
                for (int x = 0; x < segments; x++)
                {
                    int i = z * n + x;
                    tris[t++] = i; tris[t++] = i + n; tris[t++] = i + 1;
                    tris[t++] = i + 1; tris[t++] = i + n; tris[t++] = i + n + 1;
                }
            m.vertices = v;
            m.uv = uv;
            m.colors32 = cols;
            m.triangles = tris;
            m.RecalculateNormals();
            m.bounds = new Bounds(Vector3.zero, new Vector3(size, 8f, size));
            return PlaceholderMeshes.Store(name, m);
        }

        static VolumeProfile Profile()
        {
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(ProfilePath);
            if (profile == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(ProfilePath));
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                AssetDatabase.CreateAsset(profile, ProfilePath);
            }
            if (!profile.TryGet(out Tonemapping tm)) tm = profile.Add<Tonemapping>(true);
            tm.mode.Override(TonemappingMode.Neutral);
            if (!profile.TryGet(out Bloom bloom)) bloom = profile.Add<Bloom>(true);
            bloom.threshold.Override(1.15f);
            bloom.intensity.Override(0.22f);
            bloom.scatter.Override(0.55f);
            if (!profile.TryGet(out ColorAdjustments ca)) ca = profile.Add<ColorAdjustments>(true);
            ca.postExposure.Override(0.1f);
            ca.contrast.Override(8f);
            ca.saturation.Override(6f);
            foreach (var comp in profile.components) EditorUtility.SetDirty(comp);
            EditorUtility.SetDirty(profile);
            return profile;
        }
    }
}
