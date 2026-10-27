using UnityEngine;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        /// <summary>
        /// The Clean Energy Lab on the plinth top. Its boards are built at runtime from primitives; the scene only
        /// places it, hands it the palette materials, names what it hides (the miniature city) and where the player
        /// stands: a step closer to the plinth than the Atelier spot, so every block is within arm's reach in VR.
        /// </summary>
        static void BuildEnergyLab(Ctx c, MiniatureMirror mirror)
        {
            var go = Child(c.Atelier, "Clean Energy Lab", Vector3.zero);
            go.transform.position = c.PlinthTop.position + new Vector3(0f, 0.03f, 0f);
            var lab = go.AddComponent<EnergyLab>();
            lab.pearl = MaterialLibrary.Get("SKY_Pearl");
            lab.ink = MaterialLibrary.Get("SKY_Ink");
            lab.teal = MaterialLibrary.Get("SKY_Teal");
            lab.tealGlow = MaterialLibrary.Get("SKY_TealGlow");
            lab.coral = MaterialLibrary.Get("SKY_Coral");
            lab.gold = MaterialLibrary.Get("SKY_Gold");
            lab.metal = MaterialLibrary.Get("SKY_Metal");
            lab.sand = MaterialLibrary.Get("SKY_Sandstone");
            lab.sea = MaterialLibrary.Get("SKY_TealLight");
            lab.lamp = MaterialLibrary.Get("SKY_Light");
            lab.wood = MaterialLibrary.Get("SKY_Wood");
            lab.solar = MaterialLibrary.Get("SKY_Solar");
            lab.nuclear = MaterialLibrary.Get("SKY_Nuclear");
            lab.battery = MaterialLibrary.Get("SKY_Battery");
            lab.gas = MaterialLibrary.Get("SKY_Gas");
            lab.mud = MaterialLibrary.Get("SKY_Mud");
            lab.leaf = MaterialLibrary.Get("SKY_Leaf");
            lab.blue = MaterialLibrary.Get("SKY_EnergyBlue");
            lab.hideInLab = new[] { c.MiniRoot.gameObject, c.Tray.gameObject, c.MiniLine.gameObject };
            lab.mirror = mirror;

            var stand = c.Layout.GetAnchor("atelier.player");
            var spot = Child(c.Atelier, "Lab Player Spot", new Vector3(c.PlinthTop.position.x, stand.Position.y, c.PlinthTop.position.z - 0.95f), 0f);
            lab.playerSpot = spot.transform;
        }
    }
}
