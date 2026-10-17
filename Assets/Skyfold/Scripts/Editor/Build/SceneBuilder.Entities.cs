using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        static void BuildEntities(Ctx c)
        {
            var L = c.Layout;
            BuildCar(c, L);
            BuildCell(c, L);
            BuildKiosks(c, L);
            BuildAirfield(c, L);
            BuildVehicles(c, L);
            BuildOverlooks(c, L);
            BuildNuri(c, L);

            // Named anchors used as objective targets.
            foreach (var id in new[] { "substation.park", "terminal.stop" })
            {
                var a = L.GetAnchor(id);
                Named(Child(c.Entities, "Target " + id, a.Position, a.Yaw), id);
            }

            // Restrained objective marker (street only).
            var marker = Child(c.Entities, "Target Marker");
            var tm = marker.AddComponent<TargetMarker>();
            var vis = Child(marker.transform, "Visual");
            var ring = Child(vis.transform, "Ring");
            ring.AddComponent<MeshFilter>().sharedMesh = RingMesh();
            ring.AddComponent<MeshRenderer>().sharedMaterial = MaterialLibrary.Get("SKY_Marker");
            ring.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            ring.transform.localScale = new Vector3(0.5f, 1f, 0.5f);
            var chevron = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(chevron.GetComponent<Collider>());
            chevron.transform.SetParent(vis.transform, false);
            chevron.transform.localPosition = new Vector3(0f, -0.55f, 0f);
            chevron.transform.localRotation = Quaternion.Euler(0f, 0f, 45f);
            chevron.transform.localScale = new Vector3(0.28f, 0.28f, 1f);
            chevron.GetComponent<MeshRenderer>().sharedMaterial = MaterialLibrary.Get("SKY_Marker");
            tm.visual = vis.transform;
        }

        static Transform Anchor(Transform modelRoot, string name, Vector3 fallbackLocal, Transform parent)
        {
            var a = FindDeep(modelRoot, name);
            var go = Child(parent, name.Replace("ANCHOR_", "").Replace("SOCKET_", "Socket "));
            if (a != null) { go.transform.position = a.position; go.transform.rotation = a.rotation; }
            else go.transform.localPosition = fallbackLocal;
            return go.transform;
        }

        static void MirrorProxy(Ctx c, string id, Transform source, string model)
        {
            var proxy = ModelLibrary.Spawn(model, c.Atelier, Vector3.zero, 0f, CityLayout.MiniScale);
            proxy.name = "Mini " + id;
            SetLayer(proxy, "MiniCity");
            foreach (var r in proxy.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = ShadowCastingMode.Off;
            c.MirrorPairs.Add(new MiniatureMirror.Pair { id = id, source = source, proxy = proxy.transform, yawOnly = id != "aircraft" });
        }

        static void BuildCar(Ctx c, CityLayout L)
        {
            var a = L.GetAnchor("depot.car");
            var root = Child(c.Entities, "Courier Car", a.Position, a.Yaw);
            SetLayer(root, "Vehicle", false);
            var rb = root.AddComponent<Rigidbody>();
            var body = Child(root.transform, "Body");
            var model = ModelLibrary.Spawn("courier_car", body.transform, Vector3.zero);
            SetLayer(model, "Vehicle");
            var bc = root.AddComponent<BoxCollider>();
            bc.center = new Vector3(0f, 1.0f, 0f);
            bc.size = new Vector3(1.55f, 1.15f, 3.25f);

            var car = root.AddComponent<CourierVehicle>();
            car.body = body.transform;
            car.seat = Child(root.transform, "Seat").transform;
            car.eye = Anchor(model.transform, "ANCHOR_driver_eye", new Vector3(0f, 1.15f, -0.15f), root.transform);
            car.exitLeft = Anchor(model.transform, "ANCHOR_exit_left", new Vector3(-1.5f, 0f, 0f), root.transform);
            car.exitRight = Anchor(model.transform, "ANCHOR_exit_right", new Vector3(1.5f, 0f, 0f), root.transform);
            string[] wheels = { "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR" };
            for (int i = 0; i < 4; i++) car.wheels[i] = FindDeep(model.transform, wheels[i]);
            car.steeringWheel = FindDeep(model.transform, "SteeringWheel");

            // Headlights.
            var lights = new Light[2];
            for (int i = 0; i < 2; i++)
            {
                var lg = Child(root.transform, "Headlight " + i, new Vector3(i == 0 ? -0.55f : 0.55f, 0.75f, 1.7f));
                var l = lg.AddComponent<Light>();
                l.type = LightType.Spot;
                l.range = 26f;
                l.spotAngle = 62f;
                l.intensity = 3f;
                l.color = new Color(1f, 0.92f, 0.78f);
                l.shadows = LightShadows.None;
                l.enabled = false;
                lights[i] = l;
            }
            car.headlights = lights;

            // Door (use to climb in) on the left side.
            var doorAnchor = FindDeep(model.transform, "ANCHOR_door");
            var door = Child(root.transform, "Door", doorAnchor != null ? root.transform.InverseTransformPoint(doorAnchor.position) + new Vector3(0f, 0.9f, 0f) : new Vector3(-0.9f, 0.9f, 0f));
            var dc = door.AddComponent<BoxCollider>();
            dc.isTrigger = true;
            dc.size = new Vector3(0.6f, 1.2f, 1.4f);
            SetLayer(door, "Interactable", false);
            door.AddComponent<XRSimpleInteractable>();
            var cd = door.AddComponent<CarDoor>();
            cd.car = car;
            cd.verb = "Climb in";
            Named(door, "car.door");

            // Cargo cradle.
            var sock = FindDeep(model.transform, "SOCKET_cargo");
            var cradle = Child(root.transform, "Cradle", sock != null ? root.transform.InverseTransformPoint(sock.position) : new Vector3(0f, 0.72f, -1.25f));
            car.cradle = MakeSocket(cradle, CellLocation.CarCradle, "Load the cell");
            Named(cradle, "car.cradle");

            Named(root, "car");
            c.Car = car;
            MirrorProxy(c, "car", root.transform, "courier_car");
        }

        static void BuildCell(Ctx c, CityLayout L)
        {
            var d = L.GetAnchor("depot.dock");
            var dock = ModelLibrary.Spawn("cell_dock", c.Entities, d.Position, d.Yaw);
            SetStatic(dock);
            BoundsCollider(dock, 0.8f);
            var ds = FindDeep(dock.transform, "SOCKET_cell");
            var sgo = Child(dock.transform, "Dock Socket", ds != null ? dock.transform.InverseTransformPoint(ds.position) : new Vector3(0f, 0.62f, 0f));
            c.Dock = MakeSocket(sgo, CellLocation.Dock, "Put the cell back");
            Named(sgo, "dock");

            var cellGo = ModelLibrary.Spawn("power_cell", c.Entities, sgo.transform.position);
            cellGo.name = "Power Cell";
            SetLayer(cellGo, "Interactable");
            var rb = cellGo.AddComponent<Rigidbody>();
            rb.mass = 3f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            var cap = cellGo.AddComponent<CapsuleCollider>();
            cap.center = new Vector3(0f, 0.175f, 0f);
            cap.height = 0.36f;
            cap.radius = 0.075f;
            var grab = cellGo.AddComponent<XRGrabInteractable>();
            grab.movementType = XRBaseInteractable.MovementType.Instantaneous;
            grab.throwOnDetach = false;
            grab.useDynamicAttach = true;
            // XRI otherwise re-parents a dropped object to where it was picked up (the car's cradle).
            grab.retainTransformParent = false;
            var cell = cellGo.AddComponent<PowerCell>();
            cell.dock = c.Dock;
            cell.sockets = new[] { c.Dock, c.Car.cradle, c.SubstationSocket };
            var core = FindDeep(cellGo.transform, "Core");
            cell.core = core != null ? core.GetComponent<Renderer>() : null;
            cell.verb = "Pick up the power cell";
            Named(cellGo, "cell");
            c.Cell = cell;
        }

        static void BuildKiosks(Ctx c, CityLayout L)
        {
            foreach (var id in new[] { "kiosk.A", "kiosk.B" })
            {
                var a = L.GetAnchor(id);
                var k = ModelLibrary.Spawn("foldstation_kiosk", c.Entities, a.Position, a.Yaw);
                k.name = "Fold Station " + id;
                SetStatic(k);
                BoundsCollider(k, 0.7f);
                var fs = k.AddComponent<FoldStation>();
                fs.stationId = id;
                var arrive = L.GetAnchor(id + ".arrive");
                fs.arriveAnchor = Child(c.Entities, "Arrive " + id, arrive.Position, arrive.Yaw).transform;
                var ring = FindDeep(k.transform, "LensRing");
                fs.lensRing = ring != null ? ring.GetComponent<Renderer>() : null;
                Named(k, id);
                c.Stations.Add(fs);
            }
        }

        static BeaconSwitch MakeSwitch(Ctx c, string anchor, string flag, string target)
        {
            var a = c.Layout.GetAnchor(anchor);
            var go = ModelLibrary.Spawn("switch_box", c.Entities, a.Position, a.Yaw);
            go.name = "Switch " + flag;
            BoundsCollider(go, 1f);
            SetLayer(go, "Interactable");
            go.AddComponent<XRSimpleInteractable>();
            var sw = go.AddComponent<BeaconSwitch>();
            sw.flagKey = flag;
            var pivot = FindDeep(go.transform, "LeverPivot") ?? FindDeep(go.transform, "Lever");
            sw.lever = pivot;
            Named(go, target);
            return sw;
        }

        static void BuildAirfield(Ctx c, CityLayout L)
        {
            for (int i = 1; i <= 3; i++) c.Switches.Add(MakeSwitch(c, "beacon.switch." + i, Flags.BeaconPrefix + i, "switch." + i));
            c.MasterSwitch = MakeSwitch(c, "demo.beacon.switch", Flags.BeaconPrefix + "master", "switch.demo");

            var la = L.GetAnchor("tower.lever");
            var lev = ModelLibrary.Spawn("switch_box", c.Entities, la.Position, la.Yaw);
            lev.name = "Departure Lever";
            BoundsCollider(lev, 1f);
            SetLayer(lev, "Interactable");
            lev.AddComponent<XRSimpleInteractable>();
            c.Lever = lev.AddComponent<DepartureLever>();
            c.Lever.lever = FindDeep(lev.transform, "LeverPivot") ?? FindDeep(lev.transform, "Lever");
            Named(lev, "lever.departure");

            // The aircraft.
            var pa = L.GetAnchor("plane.park");
            var plane = ModelLibrary.Spawn("aircraft", c.Entities, pa.Position, pa.Yaw);
            plane.name = "Aircraft";
            BoundsCollider(plane, 0.9f);
            var seq = plane.AddComponent<AircraftSequence>();
            var props = new System.Collections.Generic.List<Transform>();
            foreach (var n in new[] { "Prop_L", "Prop_R" }) { var p = FindDeep(plane.transform, n); if (p != null) props.Add(p); }
            seq.props = props.ToArray();
            seq.door = FindDeep(plane.transform, "Door");
            seq.navLeft = PlaneLight(plane.transform, "LIGHT_nav_L", new Color(1f, 0.2f, 0.2f), new Vector3(-7.8f, 3.1f, 0.4f), LightType.Point, 6f);
            seq.navRight = PlaneLight(plane.transform, "LIGHT_nav_R", new Color(0.2f, 1f, 0.35f), new Vector3(7.8f, 3.1f, 0.4f), LightType.Point, 6f);
            seq.beacon = PlaneLight(plane.transform, "LIGHT_beacon", new Color(1f, 0.25f, 0.2f), new Vector3(0f, 3.6f, -1f), LightType.Point, 10f);
            seq.landing = PlaneLight(plane.transform, "LIGHT_landing", new Color(1f, 0.95f, 0.85f), new Vector3(0f, 1.6f, 6.4f), LightType.Spot, 60f);
            var windows = new System.Collections.Generic.List<Renderer>();
            foreach (var r in plane.GetComponentsInChildren<Renderer>()) windows.Add(r);
            seq.cabinWindows = windows.ToArray();
            for (int i = 0; i < 3; i++)
            {
                var p = ModelLibrary.Spawn(i == 0 ? "passenger_a" : i == 1 ? "passenger_b" : "passenger_c", c.Entities, Vector3.zero);
                p.name = "Passenger " + i;
                p.SetActive(false);
                seq.passengers.Add(p.transform);
            }
            Named(plane, "aircraft");
            c.Aircraft = seq;
            MirrorProxy(c, "aircraft", plane.transform, "aircraft");
        }

        static Light PlaneLight(Transform plane, string empty, Color color, Vector3 fallback, LightType type, float range)
        {
            var e = FindDeep(plane, empty);
            var go = new GameObject(empty);
            go.transform.SetParent(e != null ? e : plane, false);
            if (e == null) go.transform.localPosition = fallback;
            var l = go.AddComponent<Light>();
            l.type = type;
            l.color = color;
            l.range = range;
            l.intensity = type == LightType.Spot ? 4f : 2f;
            if (type == LightType.Spot) { l.spotAngle = 50f; go.transform.localRotation = Quaternion.Euler(8f, 0f, 0f); }
            l.shadows = LightShadows.None;
            l.enabled = false;
            return l;
        }

        static PathVehicle MakePathVehicle(Ctx c, string model, string name, Vector3 pos, float yaw, float speed)
        {
            var root = Child(c.Entities, name, pos, yaw);
            var m = ModelLibrary.Spawn(model, root.transform, Vector3.zero);
            SetLayer(root, "Vehicle");
            var rb = root.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            var b = ModelInspector.Bounds(m);
            var bc = root.AddComponent<BoxCollider>();
            bc.center = b.center;
            bc.size = b.size * 0.95f;
            var pv = root.AddComponent<PathVehicle>();
            pv.cruiseSpeed = speed;
            var wheels = new System.Collections.Generic.List<Transform>();
            foreach (var n in new[] { "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR" }) { var w = FindDeep(m.transform, n); if (w != null) wheels.Add(w); }
            pv.wheels = wheels.ToArray();
            return pv;
        }

        static void BuildVehicles(Ctx c, CityLayout L)
        {
            var bus = L.GetAnchor("bus.spawn");
            for (int i = 0; i < 2; i++)
            {
                var v = MakePathVehicle(c, "convoy_shuttle", "Convoy Shuttle " + (i + 1), bus.Position - bus.Forward * (7.5f * i), bus.Yaw, 7f);
                c.Shuttles.Add(v);
                MirrorProxy(c, "shuttle" + i, v.transform, "convoy_shuttle");
            }
            for (int i = 0; i < 4; i++)
            {
                var v = MakePathVehicle(c, i % 2 == 0 ? "city_car_a" : "city_car_b", "Traffic Car " + (i + 1), new Vector3(40f + i * 20f, 0.02f, 40f), 90f, 6.5f);
                c.Traffic.Add(v);
                MirrorProxy(c, "traffic" + i, v.transform, i % 2 == 0 ? "city_car_a" : "city_car_b");
            }
            // A few moored boats on the bay for life, riding the swell.
            // (The middle boat used to sit at (90, -38), inside the Atelier headland's rock, where nobody could see it.)
            var moorings = new[] { new Vector2(-40f, -20f), new Vector2(58f, -17f), new Vector2(220f, -56f) };
            for (int i = 0; i < (ModelLibrary.Has("dhow_small") ? moorings.Length : 0); i++)
            {
                var b = ModelLibrary.Spawn("dhow_small", c.Env, new Vector3(moorings[i].x, CityLayout.WaterLevel + 0.1f, moorings[i].y), i * 50f);
                var bob = b.AddComponent<FloatBob>();
                bob.amplitude = 0.06f;
                bob.period = 4.2f + i * 0.5f;
                bob.tilt = 1.8f;
            }
        }

        static void BuildOverlooks(Ctx c, CityLayout L)
        {
            foreach (var id in new[] { "overlook.mainland", "overlook.west", "overlook.island" })
            {
                var a = L.GetAnchor(id);
                var root = Child(c.Entities, "Overlook " + id, a.Position, a.Yaw);
                var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                disc.name = "Platform";
                disc.transform.SetParent(root.transform, false);
                disc.transform.localPosition = new Vector3(0f, -0.15f, 0f);
                disc.transform.localScale = new Vector3(4.2f, 0.15f, 4.2f);
                ModelLibrary.SetMaterial(disc, "SKY_Pearl");
                SetLayer(disc, "Ground");
                Teleportable(disc);
                var rim = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Object.DestroyImmediate(rim.GetComponent<Collider>());
                rim.name = "Rim";
                rim.transform.SetParent(root.transform, false);
                rim.transform.localPosition = new Vector3(0f, -0.32f, 0f);
                rim.transform.localScale = new Vector3(4.4f, 0.05f, 4.4f);
                ModelLibrary.SetMaterial(rim, "SKY_TealGlow");
                for (int i = 0; i < 8; i++)
                {
                    float ang = i / 8f * Mathf.PI * 2f;
                    var w = Child(root.transform, "Rail " + i, new Vector3(Mathf.Cos(ang) * 2.05f, 0.55f, Mathf.Sin(ang) * 2.05f), -ang * Mathf.Rad2Deg + 90f);
                    var bc = w.AddComponent<BoxCollider>();
                    bc.size = new Vector3(1.7f, 1.1f, 0.1f);
                }
                c.Overlooks.Add(root.transform);
            }
        }

        static void BuildNuri(Ctx c, CityLayout L)
        {
            var a = L.GetAnchor("atelier.player");
            var root = Child(c.Entities, "NURI", a.Position + new Vector3(0.6f, 1.6f, 0.9f));
            var model = ModelLibrary.Spawn("nuri", root.transform, Vector3.zero);
            var n = root.AddComponent<NuriCompanion>();
            n.body = FindDeep(model.transform, "Body");
            n.head = FindDeep(model.transform, "Head");
            n.lens = FindDeep(model.transform, "Lens");
            n.wingL = FindDeep(model.transform, "Wing_L");
            n.wingR = FindDeep(model.transform, "Wing_R");
            n.tail = FindDeep(model.transform, "Tail");
            n.lensRenderer = n.lens != null ? n.lens.GetComponent<Renderer>() : null;
            foreach (var r in model.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = ShadowCastingMode.On;
            n.atelierPerch = Child(c.Atelier, "NURI Perch", c.PlinthTop.position + new Vector3(0.95f, 0.42f, -0.1f)).transform;
            c.Nuri = n;
        }
    }
}
