using UnityEngine;

namespace Skyfold
{
    /// <summary>
    /// Everything objective predicates may read. Filled in once by GameRoot when the scene starts.
    /// Predicates only read state; they never fake progress.
    /// </summary>
    public sealed class MissionContext
    {
        public CityState City;
        public CityLayout Layout;
        public TabletopController Tabletop;
        public FoldController Fold;
        public PlayerRigs Rigs;
        public CourierVehicle Car;
        public PowerCell Cell;
        public BeaconSystem Beacons;
        public ConvoyDirector Convoy;
        public AircraftSequence Aircraft;
        public DialogueDirector Dialogue;
        public NuriCompanion Nuri;
        public RouteGuide Guide;
        public MissionDirector Director;
        public Substation Substation;

        public PlayMode Mode => Rigs != null ? Rigs.Mode : PlayMode.Desktop;
        public float ObjectiveTime => Director != null ? Director.ObjectiveElapsed : 0f;

        public Transform Target(string name) => SceneRegistry.Get(name);

        public bool PlayerNear(string target, float radius)
        {
            var t = Target(target);
            if (t == null || Rigs == null) return false;
            Vector3 a = Rigs.FeetPosition; a.y = 0f;
            Vector3 b = t.position; b.y = 0f;
            return (a - b).sqrMagnitude <= radius * radius;
        }

        public bool RouteDepotToIsland => City.HasRoute("depot", "substation");
        public bool RouteToTerminal => City.HasRoute("bus_terminal", "terminal");
    }
}
