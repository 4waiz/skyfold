using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Skyfold.EditorTools
{
    /// <summary>Dumps a prefab hierarchy with components and input action references (dev aid).</summary>
    public static class PrefabInspector
    {
        public const string StarterRig = "Assets/Samples/XR Interaction Toolkit/3.6.0/Starter Assets/Prefabs/XR Origin (XR Rig).prefab";

        public static void BatchDumpStarterRig()
        {
            Dump(StarterRig, "Logs/starter_rig_dump.txt");
            EditorApplication.Exit(0);
        }

        [MenuItem("SKYFOLD/Dev/Dump Starter Rig")]
        public static void DumpMenu() => Dump(StarterRig, "Logs/starter_rig_dump.txt");

        public static void Dump(string prefabPath, string outPath)
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            var sb = new StringBuilder();
            if (root == null) sb.AppendLine("MISSING " + prefabPath);
            else Walk(root.transform, 0, sb);
            Directory.CreateDirectory(Path.GetDirectoryName(outPath));
            File.WriteAllText(outPath, sb.ToString());
            Debug.Log("[SKYFOLD] Dumped " + prefabPath + " -> " + outPath);
        }

        static void Walk(Transform t, int depth, StringBuilder sb)
        {
            string pad = new string(' ', depth * 2);
            sb.AppendLine($"{pad}* {t.name}  (active={t.gameObject.activeSelf}, layer={t.gameObject.layer}, pos={t.localPosition})");
            foreach (var c in t.GetComponents<Component>())
            {
                if (c == null) { sb.AppendLine(pad + "   - <missing script>"); continue; }
                if (c is Transform) continue;
                sb.AppendLine($"{pad}   - {c.GetType().FullName}" + (c is Behaviour b ? (b.enabled ? "" : " [disabled]") : ""));
                var so = new SerializedObject(c);
                var it = so.GetIterator();
                bool enter = true;
                while (it.Next(enter))
                {
                    enter = true;
                    if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null)
                    {
                        var o = it.objectReferenceValue;
                        if (o is InputActionReference iar)
                            sb.AppendLine($"{pad}       {it.propertyPath} -> action '{(iar.action != null ? iar.action.actionMap?.name + "/" + iar.action.name : iar.name)}'");
                        else if (o is Component oc)
                            sb.AppendLine($"{pad}       {it.propertyPath} -> {oc.GetType().Name} on '{oc.gameObject.name}'");
                        else if (o is GameObject og)
                            sb.AppendLine($"{pad}       {it.propertyPath} -> GameObject '{og.name}'");
                        else if (o is ScriptableObject || o is Material)
                            sb.AppendLine($"{pad}       {it.propertyPath} -> {o.GetType().Name} '{o.name}'");
                    }
                    else if (it.depth <= 1 && (it.propertyType == SerializedPropertyType.Boolean || it.propertyType == SerializedPropertyType.Float || it.propertyType == SerializedPropertyType.Enum || it.propertyType == SerializedPropertyType.Integer || it.propertyType == SerializedPropertyType.LayerMask))
                    {
                        if (it.name == "m_ObjectHideFlags" || it.name == "m_Enabled" || it.name == "m_EditorHideFlags") continue;
                        string v = it.propertyType switch
                        {
                            SerializedPropertyType.Boolean => it.boolValue.ToString(),
                            SerializedPropertyType.Float => it.floatValue.ToString("0.###"),
                            SerializedPropertyType.Enum => it.enumValueIndex >= 0 && it.enumValueIndex < it.enumDisplayNames.Length ? it.enumDisplayNames[it.enumValueIndex] : it.intValue.ToString(),
                            _ => it.intValue.ToString()
                        };
                        sb.AppendLine($"{pad}       {it.propertyPath} = {v}");
                    }
                }
            }
            for (int i = 0; i < t.childCount; i++) Walk(t.GetChild(i), depth + 1, sb);
        }
    }
}
