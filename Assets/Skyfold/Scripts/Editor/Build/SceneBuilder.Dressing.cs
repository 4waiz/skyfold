using UnityEngine;
using UnityEngine.Rendering;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        /// <summary>
        /// Life on and around the bay, all clear of roads, the taxiway and the take-off path: channel
        /// buoys, sea rocks off the outer coast and under the Atelier headland, and crates at the depot.
        /// Full scale only; none of it has gameplay meaning.
        /// </summary>
        static void BuildBayDressing(Ctx c)
        {
            var root = Child(c.Env, "Bay Dressing").transform;
            float water = CityLayout.WaterLevel;

            // Buoys mark the channel (row 4) and the bay mouth below the Atelier; the bridge cells stay clear.
            if (ModelLibrary.Has("buoy"))
            {
                var buoys = new[]
                {
                    new Vector3(8f, water, 71f), new Vector3(90f, water, 73.5f), new Vector3(122f, water, 70.5f),
                    new Vector3(184f, water, 72.5f), new Vector3(-12f, water, 69f), new Vector3(204f, water, 75f),
                    new Vector3(46f, water, -14f), new Vector3(146f, water, -12f),
                };
                for (int i = 0; i < buoys.Length; i++)
                {
                    var b = ModelLibrary.Spawn("buoy", root, buoys[i], i * 47f);
                    var bob = b.AddComponent<FloatBob>();
                    bob.amplitude = 0.1f;
                    bob.period = 3.1f + (i % 3) * 0.4f;
                    bob.tilt = 4f;
                    foreach (var r in b.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = ShadowCastingMode.On;
                }
            }

            // Sea rocks: weathered outcrops off the west and east shores and at the foot of the headland.
            if (ModelLibrary.Has("rock_sea_a") && ModelLibrary.Has("rock_sea_b"))
            {
                var rocks = new (Vector3 p, float yaw, float scale)[]
                {
                    (new Vector3(-16f, water - 1.2f, 22f), 30f, 1.2f), (new Vector3(-20f, water - 1.4f, 104f), 160f, 1.5f),
                    (new Vector3(208f, water - 1.3f, 38f), 250f, 1.35f), (new Vector3(211f, water - 1.4f, 112f), 95f, 1.1f),
                    (new Vector3(66f, water - 1.0f, -38f), 200f, 1.6f), (new Vector3(126f, water - 1.2f, -42f), 320f, 1.45f),
                    (new Vector3(7f, water - 1.6f, 6f), 75f, 0.8f),
                };
                for (int i = 0; i < rocks.Length; i++)
                {
                    var r = ModelLibrary.Spawn(i % 2 == 0 ? "rock_sea_a" : "rock_sea_b", root, rocks[i].p, rocks[i].yaw, rocks[i].scale);
                    SetStatic(r);
                }
            }

            // Crates against the depot's east wall, south of the cell dock (the car leaves north, the kiosk is west).
            if (ModelLibrary.Has("crate_stack"))
            {
                foreach (var (p, yaw) in new[] { (new Vector3(143.0f, 0.15f, 24.2f), 90f), (new Vector3(142.95f, 0.15f, 21.9f), 84f) })
                {
                    var crate = ModelLibrary.Spawn("crate_stack", root, p, yaw);
                    BoundsCollider(crate, 0.96f); // solid like the buildings (Default layer)
                    SetStatic(crate);
                }
            }
        }
    }
}
