using TMPro;
using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Small builders for the Clean Energy Lab: palette primitives and world-space labels. Everything the lab
    /// shows is made from these at runtime, on the plinth, with the shared SKY_* materials the scene hands over.
    /// Sizes are in metres; a world-space TextMeshPro em is fontSize x 0.1 m (so 0.4 is a 4 cm em).
    /// </summary>
    public static class LabKit
    {
        static readonly int ColorId = Shader.PropertyToID("_BaseColor");
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        static readonly int HighlightId = Shader.PropertyToID("_Highlight");
        static MaterialPropertyBlock s_Block;

        public static GameObject Node(Transform parent, string name, Vector3 localPos, Quaternion? localRot = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = localRot ?? Quaternion.identity;
            return go;
        }

        /// <summary>A primitive with a palette material. Colliders are removed unless asked for (removed at once, so a
        /// grab or simple interactable added afterwards never collects a collider that is about to disappear).</summary>
        public static GameObject Prim(PrimitiveType type, Transform parent, string name, Vector3 localPos, Vector3 size, Material mat, bool collider = false, Quaternion? localRot = null)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (!collider)
            {
                var c = go.GetComponent<Collider>();
                if (c != null) Object.DestroyImmediate(c);
            }
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = localRot ?? Quaternion.identity;
            go.transform.localScale = size;
            var r = go.GetComponent<Renderer>();
            if (r != null && mat != null) r.sharedMaterial = mat;
            return go;
        }

        public static GameObject Box(Transform parent, string name, Vector3 localPos, Vector3 size, Material mat, bool collider = false)
            => Prim(PrimitiveType.Cube, parent, name, localPos, size, mat, collider);

        /// <summary>An upright cylinder: diameter and height in metres (Unity's cylinder is 2 m tall at scale 1).</summary>
        public static GameObject Cylinder(Transform parent, string name, Vector3 localPos, float diameter, float height, Material mat, bool collider = false)
            => Prim(PrimitiveType.Cylinder, parent, name, localPos, new Vector3(diameter, height * 0.5f, diameter), mat, collider);

        /// <summary>A cylinder lying along local X (yaw turns it).</summary>
        public static GameObject Rod(Transform parent, string name, Vector3 localPos, float diameter, float length, Material mat, float yaw = 0f)
            => Prim(PrimitiveType.Cylinder, parent, name, localPos, new Vector3(diameter, length * 0.5f, diameter), mat, false, Quaternion.Euler(0f, yaw, 90f));

        public static GameObject Sphere(Transform parent, string name, Vector3 localPos, float diameter, Material mat)
            => Prim(PrimitiveType.Sphere, parent, name, localPos, Vector3.one * diameter, mat);

        /// <summary>Rotation for text lying flat on the table, readable from the player's side (-Z), top pointing away.</summary>
        public static Quaternion Flat => Quaternion.Euler(90f, 0f, 0f);

        public static TextMeshPro Label(Transform parent, string text, Vector3 localPos, Quaternion localRot, float size, Color color,
            float width, float height, bool heading = false, TextAlignmentOptions align = TextAlignmentOptions.Center)
        {
            var go = new GameObject("Label", typeof(RectTransform));
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = localRot;
            var t = go.AddComponent<TextMeshPro>();
            var font = heading ? UIStyle.HeadingFont : UIStyle.BodyFont;
            if (font != null) t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.textWrappingMode = TextWrappingModes.Normal;
            t.richText = true;
            t.rectTransform.sizeDelta = new Vector2(width, height);
            var r = t.GetComponent<Renderer>();
            if (r != null) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return t;
        }

        /// <summary>Tints one renderer without touching its shared material (emission 0 = no glow).</summary>
        public static void Tint(Renderer r, Color color, float emission = 0f)
        {
            if (r == null) return;
            s_Block ??= new MaterialPropertyBlock();
            r.GetPropertyBlock(s_Block);
            s_Block.SetColor(ColorId, color);
            s_Block.SetColor(EmissionId, emission > 0f ? color * emission : Color.black);
            r.SetPropertyBlock(s_Block);
        }

        /// <summary>Back to the shared material's colours, keeping the interaction highlight if it is on.</summary>
        public static void ClearTint(Renderer r)
        {
            if (r == null) return;
            s_Block ??= new MaterialPropertyBlock();
            r.GetPropertyBlock(s_Block);
            float highlight = s_Block.GetFloat(HighlightId);
            s_Block.Clear();
            if (highlight > 0f) s_Block.SetFloat(HighlightId, highlight);
            r.SetPropertyBlock(s_Block.isEmpty ? null : s_Block);
        }

        public static void SetMaterial(GameObject go, Material mat)
        {
            if (go == null || mat == null) return;
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                if (r.GetComponent<TextMeshPro>() == null) r.sharedMaterial = mat;
        }

        public static void SetLayer(GameObject go, string layer)
        {
            int l = LayerMask.NameToLayer(layer);
            if (l < 0) return;
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = l;
        }

        public static string Clock(float seconds)
        {
            seconds = Mathf.Max(0f, seconds);
            int m = Mathf.FloorToInt(seconds / 60f), s = Mathf.FloorToInt(seconds % 60f);
            return $"{m}:{s:00}";
        }

        public const string CO2 = "CO<sub>2</sub>";
    }
}
