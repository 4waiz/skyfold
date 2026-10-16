using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Interaction.Toolkit.Attachment;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        static readonly (string id, ModuleType type)[] AllPieces =
        {
            ("piece.bridge", ModuleType.Bridge),
            ("piece.corner", ModuleType.Corner),
            ("piece.straight", ModuleType.Straight),
            ("piece.link.tee", ModuleType.Tee),
            ("piece.link.corner", ModuleType.Corner),
            ("piece.link.straight", ModuleType.Straight)
        };

        static void BuildAtelier(Ctx c)
        {
            var L = c.Layout;
            var center = L.GetAnchor("atelier.center");
            var plinthA = L.GetAnchor("atelier.plinth");

            // Headland and terrace. The cliff model's pivot is the terrace deck height: its plateau sits
            // 2.4 m under the deck (inside the platform's 3.5 m base) and its foot stands in the sea.
            var cliff = ModelLibrary.Spawn("cliff_headland", c.Atelier, center.Position, 20f);
            if (!ModelLibrary.Has("cliff_headland"))
            {
                cliff.transform.localPosition = new Vector3(center.Position.x, center.Position.y * 0.5f - 2f, center.Position.z);
                foreach (Transform t in cliff.transform) { t.localScale = new Vector3(26f, center.Position.y + 4f, 22f); t.localPosition = Vector3.zero; }
                ModelLibrary.SetMaterial(cliff, "SKY_SandstoneDeep");
            }
            SetStatic(cliff);
            var platform = ModelLibrary.Spawn("atelier_platform", c.Atelier, center.Position);
            SetLayer(platform, "Ground");
            MeshColliders(platform);
            Teleportable(platform);
            SetStatic(platform);
            var pergola = ModelLibrary.Spawn("atelier_pergola", c.Atelier, center.Position);
            SetStatic(pergola);
            for (int i = 0; i < 4; i++)
            {
                float a = (i * 90f + 45f) * Mathf.Deg2Rad;
                var palm = ModelLibrary.Spawn(i % 2 == 0 ? "palm_small" : "planter_box", c.Atelier, center.Position + new Vector3(Mathf.Cos(a) * 5.4f, 0f, Mathf.Sin(a) * 5.4f), i * 70f);
                SetStatic(palm);
            }
            // Safety rail ring: keeps everyone on the terrace.
            for (int i = 0; i < 16; i++)
            {
                float a = i / 16f * Mathf.PI * 2f;
                var w = Child(c.Atelier, "Terrace Wall " + i, center.Position + new Vector3(Mathf.Cos(a) * 7.1f, 0.6f, Mathf.Sin(a) * 7.1f), -a * Mathf.Rad2Deg + 90f);
                var bc = w.AddComponent<BoxCollider>();
                bc.size = new Vector3(3f, 1.2f, 0.3f);
            }

            // The plinth with its tray.
            var plinth = ModelLibrary.Spawn("plinth", c.Atelier, plinthA.Position);
            SetStatic(plinth);
            var pc = plinth.AddComponent<BoxCollider>();
            pc.center = new Vector3(0f, 0.45f, 0f);
            pc.size = new Vector3(1.6f, 0.9f, 1.2f);
            var anchor = FindDeep(plinth.transform, "ANCHOR_minicity");
            c.PlinthTop = Child(c.Atelier, "Plinth Top", plinthA.Position + Vector3.up * 0.9f).transform;
            if (anchor != null) c.PlinthTop.position = anchor.position;
            Named(c.PlinthTop.gameObject, "plinth");

            // The tray model shares the plinth origin; its SOCKET_slot_1..6 empties mark each slot floor.
            bool trayModel = ModelLibrary.Has("plinth_tray");
            var tray = ModelLibrary.Spawn("plinth_tray", c.Atelier, trayModel ? plinthA.Position : c.PlinthTop.position + new Vector3(0f, -0.02f, -0.69f));
            SetStatic(tray);
            c.Tray = tray.transform;
            var slots = new System.Collections.Generic.List<Transform>();
            for (int i = 1; i <= 6; i++)
            {
                var e = FindDeep(tray.transform, "SOCKET_slot_" + i);
                Vector3 local = e != null ? tray.transform.InverseTransformPoint(e.position) + new Vector3(0f, 0.004f, 0f) : new Vector3(-0.45f + (i - 1) * 0.18f, 0.03f, 0f);
                slots.Add(Child(c.Tray, "Slot " + i, local).transform);
            }
            // Order left to right as the player sees them from the standing spot (facing north).
            slots.Sort((a, b) => a.position.x.CompareTo(b.position.x));
            c.TraySlots = slots.ToArray();
            for (int i = 0; i < c.TraySlots.Length; i++) c.TraySlots[i].name = "Slot " + i;
            Named(tray, "tray");

            // The miniature city at 1:160, oriented exactly like the real city below.
            float s160 = CityLayout.MiniScale;
            var miniGo = new GameObject("MiniCity (1:160)");
            miniGo.transform.SetParent(c.Atelier, false);
            miniGo.transform.position = c.PlinthTop.position + new Vector3(0f, 0.03f, 0f) - CityLayout.CityCenter * s160;
            miniGo.transform.localScale = Vector3.one * s160;
            c.MiniRoot = miniGo.transform;
            c.Mini = miniGo.AddComponent<MiniCity>();
            c.Mini.tray = c.Tray;
            c.Mini.traySlots = c.TraySlots;
            BuildCity(c, c.MiniRoot, true);

            // Gold route light on the miniature.
            var lineGo = Child(c.Atelier, "Mini Route Line");
            c.MiniLine = lineGo.AddComponent<LineRenderer>();
            c.MiniLine.useWorldSpace = true;
            c.MiniLine.widthMultiplier = 0.006f;
            c.MiniLine.numCornerVertices = 3;
            c.MiniLine.textureMode = LineTextureMode.Tile;
            c.MiniLine.sharedMaterial = MaterialLibrary.Get("SKY_MiniLine");
            c.MiniLine.shadowCastingMode = ShadowCastingMode.Off;
            c.MiniLine.enabled = false;

            // Grabbable pieces (one per piece id across all missions).
            for (int i = 0; i < AllPieces.Length; i++) c.Pieces.Add(MakePiece(c, AllPieces[i].id, AllPieces[i].type, c.TraySlots[i % c.TraySlots.Length]));
        }

        static ModulePiece MakePiece(Ctx c, string id, ModuleType type, Transform slot)
        {
            float s = CityLayout.MiniScale;
            var root = new GameObject("Piece " + id);
            root.transform.SetParent(c.Atelier, false);
            root.transform.position = slot.position;
            SetLayer(root, "Interactable", false);
            var rb = root.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.Interpolate;

            var visual = ModelLibrary.Spawn(ModuleInfo.ModelName(type), root.transform, Vector3.zero, 0f, s);
            visual.name = "Visual";
            foreach (var r in visual.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = ShadowCastingMode.On;
            var b = ModelInspector.Bounds(visual);
            var bc = root.AddComponent<BoxCollider>();
            bc.center = new Vector3(0f, Mathf.Max(0.012f, b.center.y * s), 0f);
            bc.size = new Vector3(16f * s, Mathf.Max(0.03f, b.size.y * s), 16f * s);

            var grab = root.AddComponent<XRGrabInteractable>();
            grab.movementType = XRBaseInteractable.MovementType.Kinematic;
            grab.throwOnDetach = false;
            grab.useDynamicAttach = true;
            grab.trackRotation = true;
            grab.farAttachMode = InteractableFarAttachMode.Far;

            // Ghost preview lives next to the miniature (not under the piece).
            var ghost = ModelLibrary.Spawn(ModuleInfo.ModelName(type), c.Atelier, slot.position, 0f, s);
            ghost.name = "Ghost " + id;
            ModelLibrary.SetMaterial(ghost, "SKY_Ghost");
            var ghostRenderers = ghost.GetComponentsInChildren<Renderer>();
            foreach (var r in ghostRenderers) r.shadowCastingMode = ShadowCastingMode.Off;
            ghost.SetActive(false);

            var piece = root.AddComponent<ModulePiece>();
            piece.pieceId = id;
            piece.type = type;
            piece.visual = visual.transform;
            piece.ghost = ghost.transform;
            piece.ghostRenderers = ghostRenderers;
            piece.homeSlot = slot;
            Named(root, id);
            return piece;
        }
    }
}
