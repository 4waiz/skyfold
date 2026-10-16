using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Restrained directional guide: small glowing chevrons on the road along the real route, and a
    /// gold light running along the same route on the miniature whenever it is connected.
    /// </summary>
    public sealed class RouteGuide : MonoBehaviour
    {
        public static RouteGuide Instance { get; private set; }

        public Material markerMaterial;
        public Material miniLineMaterial;
        public float spacing = 5f;
        public int poolSize = 120;
        public LineRenderer miniLine;

        CityState m_City;
        readonly List<Transform> m_Pool = new List<Transform>();
        readonly List<Vector3> m_Points = new List<Vector3>();
        readonly List<float> m_Dist = new List<float>();
        string m_From, m_To;
        bool m_Showing;
        Mesh m_Chevron;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        void Awake()
        {
            Instance = this;
            m_Block = new MaterialPropertyBlock();
            m_Chevron = BuildChevron();
            for (int i = 0; i < poolSize; i++)
            {
                var go = new GameObject("Guide " + i);
                go.transform.SetParent(transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = m_Chevron;
                var r = go.AddComponent<MeshRenderer>();
                r.sharedMaterial = markerMaterial;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                go.SetActive(false);
                m_Pool.Add(go.transform);
            }
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (m_City != null) m_City.RouteChanged -= OnRouteChanged;
        }

        public void Bind(CityState city)
        {
            if (m_City != null) m_City.RouteChanged -= OnRouteChanged;
            m_City = city;
            m_City.RouteChanged += OnRouteChanged;
            OnRouteChanged();
        }

        static Mesh BuildChevron()
        {
            var m = new Mesh { name = "GuideChevron" };
            float w = 0.9f, l = 0.55f, t = 0.32f;
            var v = new[]
            {
                new Vector3(-w, 0f, -l), new Vector3(0f, 0f, l - t), new Vector3(0f, 0f, l),
                new Vector3(-w, 0f, -l + t), new Vector3(w, 0f, -l), new Vector3(w, 0f, -l + t)
            };
            m.vertices = v;
            m.triangles = new[] { 0, 3, 1, 3, 2, 1, 1, 2, 5, 1, 5, 4 };
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        public void ShowRoute(string fromPoi, string toPoi)
        {
            m_From = fromPoi;
            m_To = toPoi;
            m_Showing = true;
            Rebuild();
        }

        public void Hide()
        {
            m_Showing = false;
            foreach (var t in m_Pool) t.gameObject.SetActive(false);
        }

        void OnRouteChanged()
        {
            if (m_Showing) Rebuild();
            RebuildMini();
        }

        void Rebuild()
        {
            foreach (var t in m_Pool) t.gameObject.SetActive(false);
            m_Points.Clear();
            m_Dist.Clear();
            var cells = m_City.FindRoute(m_From, m_To);
            if (cells == null) return;
            var pts = RouteValidator.PathToWorld(cells, 0f, 0.06f);
            float acc = 0f;
            for (int i = 0; i < pts.Count; i++)
            {
                if (i > 0) acc += Vector3.Distance(pts[i - 1], pts[i]);
                m_Points.Add(pts[i]);
                m_Dist.Add(acc);
            }
            int n = 0;
            for (float d = 4f; d < acc - 2f && n < m_Pool.Count; d += spacing, n++)
            {
                Sample(d, out var p, out var dir);
                var t = m_Pool[n];
                t.position = p;
                t.rotation = Quaternion.LookRotation(dir);
                t.gameObject.SetActive(true);
            }
        }

        void Sample(float d, out Vector3 p, out Vector3 dir)
        {
            for (int i = 1; i < m_Points.Count; i++)
            {
                if (m_Dist[i] >= d)
                {
                    float seg = m_Dist[i] - m_Dist[i - 1];
                    float t = seg > 0.001f ? (d - m_Dist[i - 1]) / seg : 0f;
                    p = Vector3.Lerp(m_Points[i - 1], m_Points[i], t);
                    dir = (m_Points[i] - m_Points[i - 1]).normalized;
                    return;
                }
            }
            p = m_Points[m_Points.Count - 1];
            dir = Vector3.forward;
        }

        void RebuildMini()
        {
            if (miniLine == null || m_City == null || MiniCity.Instance == null) return;
            var cells = m_City.FindRoute("depot", "substation");
            if (cells == null) { miniLine.enabled = false; return; }
            var pts = RouteValidator.PathToWorld(cells, 0f, 0.9f);
            miniLine.positionCount = pts.Count;
            for (int i = 0; i < pts.Count; i++) miniLine.SetPosition(i, MiniCity.Instance.CityToWorld(pts[i]));
            miniLine.enabled = true;
        }

        void Update()
        {
            // A pulse travels forward along the chevrons; ones behind the player fade out.
            if (m_Showing)
            {
                var rigs = PlayerRigs.Instance;
                Vector3 player = rigs != null ? (rigs.IsDriving && CourierVehicle.Instance != null ? CourierVehicle.Instance.Position : rigs.FeetPosition) : Vector3.zero;
                float pulse = Mathf.Repeat(Time.time * 18f, 60f);
                for (int i = 0; i < m_Pool.Count; i++)
                {
                    var t = m_Pool[i];
                    if (!t.gameObject.activeSelf) continue;
                    float dPlayer = Vector3.Distance(t.position, player);
                    float k = Mathf.Repeat(i * spacing - pulse, 60f) < 6f ? 3.2f : 1.1f;
                    if (dPlayer > 140f) k *= 0.3f;
                    var r = t.GetComponent<MeshRenderer>();
                    r.GetPropertyBlock(m_Block);
                    m_Block.SetColor(EmissionId, new Color(0.85f, 0.64f, 0.25f) * k);
                    r.SetPropertyBlock(m_Block);
                }
            }
            if (miniLine != null && miniLine.enabled && miniLine.sharedMaterial != null)
                miniLine.sharedMaterial.mainTextureOffset = new Vector2(-Time.time * 1.2f, 0f);
        }
    }
}
