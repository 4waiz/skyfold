namespace Skyfold
{
    /// <summary>The courier car's side opening: use it to climb in.</summary>
    public sealed class CarDoor : WorldInteractable
    {
        public CourierVehicle car;

        public override bool CanInteract(InteractorKind who) => base.CanInteract(who) && car != null && !car.HasDriver && !car.Busy;
        public override string Prompt => "Climb in";
        public override string BlockedReason
        {
            get
            {
                if (car == null) return null;
                return car.CanEnter(out var reason) ? null : reason;
            }
        }

        public override void Interact(InteractorKind who) => car?.RequestEnter();
    }
}
