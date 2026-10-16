using UnityEngine;
using UnityEngine.Rendering;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        /// <summary>
        /// Builds the city grid under root in city coordinates (1 unit = 1 m). Full scale gets
        /// colliders, teleport areas, lamps and sea walls; the miniature gets the same silhouettes.
        /// </summary>
        static void BuildCity(Ctx c, Transform root, bool mini)
        {
            var L = c.Layout;
            var rng = new System.Random(mini ? 77 : 1607);
            for (int x = 0; x < L.Width; x++)
            {
                for (int z = 0; z < L.Height; z++)
                {
                    var cell = new Vector2Int(x, z);
                    var kind = L.Kind(cell);
                    var pos = CityLayout.CellCenter(cell);
                    var cellRoot = Child(root, $"Cell {x},{z} {kind}", pos);
                    switch (kind)
                    {
                        case CellKind.Road:
                            {
                                var t = L.FixedType(cell);
                                var go = ModelLibrary.Spawn(ModuleInfo.ModelName(t), cellRoot.transform, Vector3.zero, L.FixedRotation(cell) * 90f);
                                Ground(go, mini, true);
                                if (!mini && (x + z) % 2 == 0) Lamp(c, cellRoot.transform, L.FixedType(cell), L.FixedRotation(cell), z >= 5);
                                break;
                            }
                        case CellKind.Socket:
                            BuildSocketCell(c, cellRoot.transform, L.SocketAt(cell), mini);
                            break;
                        case CellKind.Water:
                            break;
                        case CellKind.Lot:
                        case CellKind.Shore:
                            {
                                var g = ModelLibrary.Spawn("ground_paving", cellRoot.transform, new Vector3(0f, 0.15f, 0f));
                                Ground(g, mini, true);
                                string model = null; int rot = 0;
                                foreach (var lot in L.Lots) if (lot.Cell == cell) { model = lot.Model; rot = lot.Rotation; }
                                if (model != null)
                                {
                                    var b = ModelLibrary.Spawn(model, cellRoot.transform, new Vector3(0f, 0.15f, 0f), rot * 90f);
                                    if (!mini) { BoundsCollider(b); WindowsForIsland(c, b, z >= 5); }
                                    SetStatic(b);
                                    Dress(c, cellRoot.transform, rng, mini, 1, 2);
                                }
                                else Dress(c, cellRoot.transform, rng, mini, kind == CellKind.Shore ? 3 : 2, 4);
                                break;
                            }
                        case CellKind.Plaza:
                            {
                                var g = ModelLibrary.Spawn("road_plaza", cellRoot.transform, Vector3.zero);
                                Ground(g, mini, true);
                                ModelLibrary.Spawn("fountain_small", cellRoot.transform, new Vector3(0f, 0.15f, 0f));
                                Dress(c, cellRoot.transform, rng, mini, 2, 3);
                                if (!mini) for (int i = 0; i < 2; i++) ModelLibrary.Spawn("bench", cellRoot.transform, new Vector3(i == 0 ? -4f : 4f, 0.15f, -4f), i == 0 ? 90f : 270f);
                                break;
                            }
                        case CellKind.Runway:
                            {
                                bool end = x == 1 || x == 10;
                                var g = ModelLibrary.Spawn(end ? "runway_end" : "runway_section", cellRoot.transform, Vector3.zero, end ? (x == 1 ? 270f : 90f) : 90f);
                                Ground(g, mini, true);
                                break;
                            }
                        case CellKind.Apron:
                            {
                                var g = ModelLibrary.Spawn("apron_tile", cellRoot.transform, Vector3.zero);
                                Ground(g, mini, true);
                                break;
                            }
                        case CellKind.Poi:
                            BuildPoiCell(c, cellRoot.transform, L.PoiAt(cell), mini);
                            break;
                    }
                }
            }
            BuildQuays(c, root, mini);
            if (!mini) BuildRunwayExtras(c, root);
        }

        static void Ground(GameObject go, bool mini, bool walkable)
        {
            SetStatic(go);
            if (mini) { SetLayer(go, "MiniCity"); return; }
            SetLayer(go, "Ground");
            MeshColliders(go);
            if (walkable) Teleportable(go);
        }

        static void Lamp(Ctx c, Transform cell, ModuleType type, int rot, bool island)
        {
            // Put the lamp on a sidewalk side (a side with no opening).
            var open = ModuleInfo.Openings(type, rot);
            foreach (var d in DirUtil.All)
            {
                if (open.Has(d)) continue;
                Vector3 p = d.Forward() * 6.4f + Vector3.up * 0.15f + Quaternion.Euler(0, 90, 0) * d.Forward() * 3f;
                var lamp = ModelLibrary.Spawn("street_lamp", cell, p, ((int)d * 90f) + 180f);
                var col = lamp.AddComponent<CapsuleCollider>();
                col.center = new Vector3(0f, 2.5f, 0f);
                col.height = 5f;
                col.radius = 0.15f;
                SetStatic(lamp);
                if (island)
                {
                    var lgo = Child(lamp.transform, "Lamp Light", new Vector3(0f, 4.8f, 0f));
                    var l = lgo.AddComponent<Light>();
                    l.type = LightType.Point;
                    l.range = 11f;
                    l.intensity = 2.2f;
                    l.color = new Color(1f, 0.82f, 0.58f);
                    l.shadows = LightShadows.None;
                    l.enabled = false;
                    c.IslandLights.Add(l);
                }
                return;
            }
        }

        static void WindowsForIsland(Ctx c, GameObject building, bool island)
        {
            if (!island) return;
            foreach (var r in building.GetComponentsInChildren<Renderer>())
                foreach (var m in r.sharedMaterials)
                    if (m != null && (m.name == "SKY_Light" || m.name == "SKY_Glass")) { c.IslandWindows.Add(r); break; }
        }

        static void Dress(Ctx c, Transform cell, System.Random rng, bool mini, int min, int max)
        {
            int n = rng.Next(min, max + 1);
            string[] options = { "palm_date_a", "palm_date_b", "palm_small", "planter_box", "shrub_round", "bougainvillea_clump" };
            for (int i = 0; i < n; i++)
            {
                // Corners of the plot keep clear of buildings and roads.
                float sx = (i % 2 == 0 ? -1f : 1f) * (6.2f + (float)rng.NextDouble() * 0.8f);
                float sz = (i / 2 % 2 == 0 ? -1f : 1f) * (6.2f + (float)rng.NextDouble() * 0.8f);
                string m = options[rng.Next(mini ? 3 : options.Length)];
                var go = ModelLibrary.Spawn(m, cell, new Vector3(sx, 0.15f, sz), (float)rng.NextDouble() * 360f, 0.85f + (float)rng.NextDouble() * 0.3f);
                SetStatic(go);
                if (mini) SetLayer(go, "MiniCity");
                else if (m.StartsWith("palm"))
                {
                    var col = go.AddComponent<CapsuleCollider>();
                    col.center = new Vector3(0f, 2f, 0f);
                    col.height = 4f;
                    col.radius = 0.25f;
                }
            }
        }

        static void BuildSocketCell(Ctx c, Transform cell, SocketDef s, bool mini)
        {
            var slotGo = Child(cell, "Slot " + s.Id);
            var slot = slotGo.AddComponent<FullScaleSlot>();
            slot.socketId = s.Id;

            GameObject stub;
            if (s.Water) stub = ModelLibrary.Spawn("bridge_stub", slotGo.transform, Vector3.zero);
            else
            {
                stub = Child(slotGo.transform, "Broken ground");
                var g = ModelLibrary.Spawn("ground_paving", stub.transform, new Vector3(0f, 0.02f, 0f));
                if (!mini)
                {
                    ModelLibrary.Spawn("barrier_coral", stub.transform, new Vector3(-3.5f, 0.05f, 0f), 90f);
                    ModelLibrary.Spawn("barrier_coral", stub.transform, new Vector3(3.5f, 0.05f, 0f), 90f);
                    ModelLibrary.Spawn("traffic_cone", stub.transform, new Vector3(0f, 0.05f, 3f));
                    ModelLibrary.Spawn("traffic_cone", stub.transform, new Vector3(0f, 0.05f, -3f));
                }
            }
            stub.name = "Stub";
            slot.brokenStub = stub;
            if (mini) SetLayer(stub, "MiniCity");
            else { SetLayer(stub, "Ground"); MeshColliders(stub); }

            if (mini)
            {
                // The miniature shows the gap and a socket ring; the player's piece sits on top.
                var sockGo = Child(cell, "Mini Socket " + s.Id, new Vector3(0f, 0.6f, 0f));
                var ts = sockGo.AddComponent<TileSocket>();
                ts.socketId = s.Id;
                var ringGo = Child(sockGo.transform, "Ring");
                ringGo.AddComponent<MeshFilter>().sharedMesh = RingMesh();
                var rr = ringGo.AddComponent<MeshRenderer>();
                rr.sharedMaterial = MaterialLibrary.Get("SKY_Ring");
                rr.shadowCastingMode = ShadowCastingMode.Off;
                ringGo.transform.localScale = new Vector3(7.4f, 1f, 7.4f);
                ts.ring = rr;
                var icon = Child(sockGo.transform, "Icon", new Vector3(0f, 6f, 0f));
                ts.iconAnchor = icon.transform;
                ts.iconValid = IconQuad(icon.transform, "Valid", "SKY_IconCheck");
                ts.iconInvalid = IconQuad(icon.transform, "Invalid", "SKY_IconCross");
                Named(sockGo, "socket." + s.Id);
                SetLayer(sockGo, "MiniCity");
                c.Slots.Add(slot);
                return;
            }

            // Full scale: pre-built variants the CityState can switch on.
            var types = s.Water ? new[] { ModuleType.Bridge } : new[] { ModuleType.Straight, ModuleType.Corner, ModuleType.Tee, ModuleType.Cross };
            foreach (var t in types)
            {
                var v = ModelLibrary.Spawn(ModuleInfo.ModelName(t), slotGo.transform, Vector3.zero);
                v.name = "Variant " + t;
                SetLayer(v, "Ground");
                MeshColliders(v);
                Teleportable(v);
                v.SetActive(false);
                slot.variants.Add(new FullScaleSlot.Variant { type = t, root = v });
            }
            var lightGo = Child(slotGo.transform, "Build Light", new Vector3(0f, 6f, 0f));
            var bl = lightGo.AddComponent<Light>();
            bl.type = LightType.Point;
            bl.range = 22f;
            bl.color = new Color(0.4f, 0.95f, 0.9f);
            bl.enabled = false;
            slot.buildLight = bl;
            c.Slots.Add(slot);
        }

        static Renderer IconQuad(Transform parent, string name, string material)
        {
            var q = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(q.GetComponent<Collider>());
            q.name = name;
            q.transform.SetParent(parent, false);
            q.transform.localScale = new Vector3(7f, 7f, 7f);
            var r = q.GetComponent<MeshRenderer>();
            r.sharedMaterial = MaterialLibrary.Get(material);
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.enabled = false;
            return r;
        }

        static Mesh s_Ring;
        static Mesh RingMesh()
        {
            if (s_Ring != null) return s_Ring;
            var existing = UnityEditor.AssetDatabase.LoadAssetAtPath<Mesh>(PlaceholderMeshes.Folder + "/SocketRing.asset");
            if (existing != null) return s_Ring = existing;
            const int seg = 48;
            var m = new Mesh { name = "SocketRing" };
            var v = new Vector3[seg * 2];
            var tri = new int[seg * 6];
            var col = new Color32[seg * 2];
            for (int i = 0; i < seg; i++)
            {
                float a = i / (float)seg * Mathf.PI * 2f;
                var dir = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
                v[i * 2] = dir * 0.86f;
                v[i * 2 + 1] = dir * 1f;
                col[i * 2] = col[i * 2 + 1] = new Color32(255, 255, 255, 255);
                int n = (i + 1) % seg;
                tri[i * 6] = i * 2; tri[i * 6 + 1] = n * 2; tri[i * 6 + 2] = i * 2 + 1;
                tri[i * 6 + 3] = i * 2 + 1; tri[i * 6 + 4] = n * 2; tri[i * 6 + 5] = n * 2 + 1;
            }
            m.vertices = v;
            m.triangles = tri;
            m.colors32 = col;
            m.RecalculateNormals();
            return s_Ring = PlaceholderMeshes.Store("SocketRing", m);
        }

        static void BuildPoiCell(Ctx c, Transform cell, PoiDef p, bool mini)
        {
            var apron = ModelLibrary.Spawn("apron_tile", cell, Vector3.zero);
            Ground(apron, mini, true);
            // The building sits on the side away from the road opening.
            Dir open = Dir.N;
            foreach (var d in DirUtil.All) if (p.Openings.Has(d)) open = d;
            Vector3 back = -open.Forward() * 3.2f;
            float yaw = (int)open * 90f; // facade toward the opening
            string model = p.Id == "depot" ? "bldg_depot" : p.Id == "substation" ? "bldg_substation" : p.Id == "terminal" ? "bldg_terminal" : "bldg_shoprow";
            var b = ModelLibrary.Spawn(model, cell, back + Vector3.up * 0.02f, yaw);
            SetStatic(b);
            if (mini) { SetLayer(b, "MiniCity"); return; }
            if (p.Id != "substation") BoundsCollider(b);
            if (p.Id == "terminal") WindowsForIsland(c, b, true);
            if (p.Id == "substation")
            {
                // A box collider would swallow the socket; use mesh colliders here.
                MeshColliders(b);
                c.Substation = b.AddComponent<Substation>();
                foreach (var r in b.GetComponentsInChildren<Renderer>(true))
                    if (r.name.Contains("PowerLights")) c.Substation.powerLights.Add(r);
                var sock = FindDeep(b.transform, "SOCKET_cell");
                var sgo = Child(sock != null ? sock : b.transform, "Substation Socket", sock != null ? Vector3.zero : new Vector3(0f, 1.1f, 5.4f));
                c.SubstationSocket = MakeSocket(sgo, CellLocation.Substation, "Insert the cell");
                c.SubstationSocket.lockWhenFilled = true;
                c.Substation.socket = c.SubstationSocket;
                Named(sgo, "substation.socket");
            }
            if (p.Id == "depot") Named(b, "depot");
        }

        static CellSocket MakeSocket(GameObject go, CellLocation location, string verb)
        {
            var col = go.AddComponent<SphereCollider>();
            col.isTrigger = true;
            col.radius = 0.32f;
            SetLayer(go, "Interactable", false);
            var s = go.AddComponent<CellSocket>();
            s.location = location;
            s.attach = go.transform;
            s.verb = verb;
            // Glowing ring so the target reads at a glance.
            var ring = Child(go.transform, "Socket Glow", new Vector3(0f, -0.02f, 0f));
            ring.AddComponent<MeshFilter>().sharedMesh = RingMesh();
            var rr = ring.AddComponent<MeshRenderer>();
            rr.sharedMaterial = MaterialLibrary.Get("SKY_TealGlow");
            rr.shadowCastingMode = ShadowCastingMode.Off;
            ring.transform.localScale = new Vector3(0.16f, 1f, 0.16f);
            s.glow = rr;
            return s;
        }

        static void BuildQuays(Ctx c, Transform root, bool mini)
        {
            var L = c.Layout;
            var quays = Child(root, "Quays").transform;
            for (int x = 0; x < L.Width; x++)
                for (int z = 0; z < L.Height; z++)
                {
                    var cell = new Vector2Int(x, z);
                    if (!L.IsLand(cell)) continue;
                    var open = CityOpenings(L, cell);
                    var waterSides = DirMask.None;
                    foreach (var d in DirUtil.All)
                    {
                        var n = cell + d.Offset();
                        bool water = !L.InBounds(n) || L.IsWater(n);
                        if (!water) continue;
                        // Roads that continue onto a bridge socket keep their edge open.
                        if (L.InBounds(n) && L.Kind(n) == CellKind.Socket && open.Has(d)) continue;
                        waterSides |= d.Mask();
                    }
                    if (waterSides == DirMask.None) continue;
                    Vector3 center = CityLayout.CellCenter(cell);
                    foreach (var d in DirUtil.All)
                    {
                        if (!waterSides.Has(d)) continue;
                        float yaw = d == Dir.S ? 0f : d == Dir.N ? 180f : d == Dir.E ? 270f : 90f;
                        var q = ModelLibrary.Spawn("quay_straight", quays, center + Vector3.up * 0.15f, yaw);
                        SetStatic(q);
                        if (mini) { SetLayer(q, "MiniCity"); continue; }
                        SetLayer(q, "Ground");
                        // Generous invisible sea wall so the car stays ashore.
                        var wall = Child(quays, "Sea Wall", center + d.Forward() * 7.9f + Vector3.up * 0.75f, yaw);
                        var bc = wall.AddComponent<BoxCollider>();
                        bc.size = new Vector3(16.2f, 1.5f, 0.4f);
                    }
                }

            if (!mini) return;
            // Miniature land blocks and sea basin: a tactile diorama cut.
            var blocks = Child(root, "Diorama").transform;
            for (int x = 0; x < L.Width; x++)
                for (int z = 0; z < L.Height; z++)
                {
                    var cell = new Vector2Int(x, z);
                    if (!L.IsLand(cell)) continue;
                    var b = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    Object.DestroyImmediate(b.GetComponent<Collider>());
                    b.name = "Land " + x + "," + z;
                    b.transform.SetParent(blocks, false);
                    b.transform.localPosition = CityLayout.CellCenter(cell) + new Vector3(0f, -2.2f, 0f);
                    b.transform.localScale = new Vector3(16f, 3.9f, 16f);
                    b.GetComponent<MeshRenderer>().sharedMaterial = MaterialLibrary.Get("SKY_SandstoneDeep");
                    SetLayer(b, "MiniCity");
                    SetStatic(b);
                }
            var basin = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(basin.GetComponent<Collider>());
            basin.name = "Sea Basin";
            basin.transform.SetParent(blocks, false);
            basin.transform.localPosition = CityLayout.CityCenter + new Vector3(0f, -4.1f, 0f);
            basin.transform.localScale = new Vector3(12 * 16f + 24f, 0.4f, 9 * 16f + 24f);
            basin.GetComponent<MeshRenderer>().sharedMaterial = MaterialLibrary.Get("SKY_Seabed");
            SetLayer(basin, "MiniCity");
            var miniSea = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(miniSea.GetComponent<Collider>());
            miniSea.name = "Mini Sea";
            miniSea.transform.SetParent(blocks, false);
            miniSea.transform.localPosition = CityLayout.CityCenter + new Vector3(0f, CityLayout.WaterLevel, 0f);
            miniSea.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            miniSea.transform.localScale = new Vector3(12 * 16f + 24f, 9 * 16f + 24f, 1f);
            miniSea.GetComponent<MeshRenderer>().sharedMaterial = MaterialLibrary.Get("SKY_Water");
            SetLayer(miniSea, "MiniCity");
        }

        static DirMask CityOpenings(CityLayout L, Vector2Int cell)
        {
            var k = L.Kind(cell);
            if (k == CellKind.Road) return ModuleInfo.Openings(L.FixedType(cell), L.FixedRotation(cell));
            if (k == CellKind.Poi) return L.PoiAt(cell).Openings;
            if (k == CellKind.Socket) return DirMask.All;
            return DirMask.None;
        }

        static void BuildRunwayExtras(Ctx c, Transform root)
        {
            // Runway edge beacons in three groups (one per switch).
            var beacons = Child(root, "Runway Beacons").transform;
            for (int g = 0; g < 3; g++) c.BeaconGroups.Add(new BeaconSystem.Group());
            for (int i = 0; i < 10; i++)
            {
                float x = 24f + i * 16f;
                int g = x < 72f ? 0 : x < 120f ? 1 : 2;
                foreach (float z in new[] { 129.6f, 142.4f })
                {
                    var b = ModelLibrary.Spawn("runway_beacon", beacons, new Vector3(x, 0.02f, z));
                    var lens = FindDeep(b.transform, "Lens");
                    var r = lens != null ? lens.GetComponent<Renderer>() : b.GetComponentInChildren<Renderer>();
                    if (r != null) c.BeaconGroups[g].lenses.Add(r);
                }
                if (i % 3 == 1)
                {
                    var lgo = Child(beacons, "Beacon Light " + i, new Vector3(x, 1.2f, 136f));
                    var l = lgo.AddComponent<Light>();
                    l.type = LightType.Point;
                    l.range = 18f;
                    l.intensity = 2.5f;
                    l.color = new Color(1f, 0.82f, 0.42f);
                    l.shadows = LightShadows.None;
                    l.enabled = false;
                    c.BeaconGroups[g].lights.Add(l);
                }
            }
        }
    }
}
