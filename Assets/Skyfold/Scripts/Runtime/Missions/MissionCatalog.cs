using System.Collections.Generic;
using UnityEngine;

namespace Skyfold
{
    /// <summary>The three campaign episodes and the three-minute demo, all on the same world and systems.</summary>
    public static class MissionCatalog
    {
        public const string Episode1 = "ep1_causeway";
        public const string Episode2 = "ep2_courier";
        public const string Episode3 = "ep3_lastflight";
        public const string Demo = "demo";

        public static MissionDefinition Get(string id)
        {
            switch (id)
            {
                case Episode1: return BuildEpisode1();
                case Episode2: return BuildEpisode2();
                case Episode3: return BuildEpisode3();
                case Demo: return BuildDemo();
                default: return BuildEpisode1();
            }
        }

        public static string ForEpisode(int episode) =>
            episode <= 1 ? Episode1 : episode == 2 ? Episode2 : Episode3;

        public static readonly string[] CampaignOrder = { Episode1, Episode2, Episode3 };

        // ---------------------------------------------------------------- shared steps
        static ObjectiveDef StepGrab(string targetPiece) => new ObjectiveDef
        {
            Id = "t.grab",
            TextVR = "Pick up the bridge piece (grip)",
            TextDesktop = "Pick up the bridge piece (left mouse)",
            Voice = "t.grab",
            PausesStorm = true,
            GuideTarget = targetPiece,
            Hints = new[]
            {
                "The bridge span is the long piece with railings, on the tray at the front of the plinth.",
                "Point at it and squeeze the grip (VR), or click and hold it (desktop)."
            },
            IsComplete = c => c.Tabletop.AnyPieceHeld || c.City.PlacedCount > 0
        };

        static ObjectiveDef StepPlace() => new ObjectiveDef
        {
            Id = "t.place",
            TextVR = "Set it into a glowing socket",
            TextDesktop = "Drop it on a glowing socket (R turns it)",
            Voice = "t.place",
            PausesStorm = true,
            GuideTarget = "socket.nearest",
            Hints = new[]
            {
                "Teal rings mark the broken links. Hold the piece over one to see a preview.",
                "A tick means it fits. If you see a cross, turn the piece a quarter and try again."
            },
            IsComplete = c => c.City.PlacedCount > 0
        };

        static ObjectiveDef StepFold(string text) => new ObjectiveDef
        {
            Id = "t.fold",
            TextVR = text + " (press X)",
            TextDesktop = text + " (press Q)",
            Voice = "t.fold",
            PausesStorm = true,
            GuideTarget = "plinth",
            Hints = new[] { "You can fold anywhere on the Atelier terrace. The prompt shows the button." },
            IsComplete = c => c.Fold.InStreet
        };

        static ObjectiveDef StepEnterCar() => new ObjectiveDef
        {
            Id = "t.enter",
            TextVR = "Climb into the courier car (point at the door, trigger)",
            TextDesktop = "Climb into the courier car (E at the door)",
            Voice = "t.enter",
            PausesStorm = true,
            GuideTarget = "car.door",
            Hints = new[] { "Walk up to the left side of the car until the prompt appears." },
            IsComplete = c => c.Car.HasDriver
        };

        static ObjectiveDef StepLoadCell() => new ObjectiveDef
        {
            Id = "t.cell",
            TextVR = "Put the power cell into the car's cradle",
            TextDesktop = "Load the power cell into the car (E)",
            Voice = "t.cell",
            PausesStorm = true,
            Checkpoint = true,
            GuideTarget = "cell",
            Hints = new[]
            {
                "The power cell glows teal on its dock beside the depot door.",
                "The cradle is the open rack at the back of the car."
            },
            IsComplete = c => c.Cell.Location == CellLocation.CarCradle
        };

        static ObjectiveDef StepDeliver() => new ObjectiveDef
        {
            Id = "e2.deliver",
            TextVR = "Put the cell into the substation socket",
            TextDesktop = "Carry the cell to the substation socket (E)",
            Voice = "e2.deliver",
            Checkpoint = true,
            GuideTarget = "substation.socket",
            Hints = new[] { "Climb out first (B or E), take the cell from the cradle, then set it into the glowing socket." },
            IsComplete = c => c.Cell.Location == CellLocation.Substation,
            OnComplete = c => c.Dialogue.Play("e2.powered")
        };

        static string MedalFor(MissionResult r, bool shortcutMatters)
        {
            if (!r.Success) return "";
            float frac = r.StormSeconds > 0 ? r.TimeLeft / r.StormSeconds : 1f;
            bool clean = r.Rejected <= 2 && r.HintsShown <= 1 && r.Retries == 0;
            if (frac >= 0.4f && clean && (!shortcutMatters || r.UsedShortcut)) return "Gold";
            if (frac >= 0.15f) return "Silver";
            return "Bronze";
        }

        static PieceDef P(string id, ModuleType t) => new PieceDef(id, t);

        // ---------------------------------------------------------------- Episode 1
        static MissionDefinition BuildEpisode1()
        {
            var m = new MissionDefinition
            {
                Id = Episode1,
                Episode = 1,
                Title = "The Broken Causeway",
                Subtitle = "Episode 1",
                Briefing = "Rebuild a crossing to the island, then drive across it.",
                StormSeconds = 360f,
                Start = StartLocation.Atelier,
                ReturnKiosk = "kiosk.A",
                ActiveSockets = new[] { "bridge_west", "bridge_east", "harbour_corner" },
                Inventory = new List<PieceDef>
                {
                    P("piece.bridge", ModuleType.Bridge),
                    P("piece.corner", ModuleType.Corner),
                    P("piece.straight", ModuleType.Straight)
                },
                IntroVoice = new[] { "e1.welcome", "e1.plinth" },
                MedalRulesText = "Gold: east shortcut, 40% storm time left, at most 2 rejected placements and 1 hint, no retries. Silver: 15% time left. Bronze: complete."
            };
            m.MedalFor = r => MedalFor(r, true);

            m.Objectives.Add(StepGrab("piece.bridge"));
            m.Objectives.Add(StepPlace());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e1.route",
                Text = "Connect the Depot to the island",
                Voice = "e1.choice",
                GuideTarget = "socket.nearest",
                Hints = new[]
                {
                    "West: one bridge, long drive. East: the bridge plus the harbour corner, short drive.",
                    "The harbour corner has to turn from the avenue towards the east crossing.",
                    "Pick a placed piece back up to move it. Nothing is ever used up."
                },
                HintDelay = 30f,
                IsComplete = c => c.RouteDepotToIsland,
                OnComplete = c =>
                {
                    var route = c.City.FindRoute("depot", "substation");
                    bool east = c.City.RouteUsesSocket(route, "bridge_east");
                    c.Dialogue.Play(east ? "e1.route_east" : "e1.route_west");
                }
            });
            m.Objectives.Add(StepFold("Fold down into the street"));
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "t.walk",
                Text = "Walk to the courier car",
                Voice = "t.walk",
                PausesStorm = true,
                Checkpoint = true,
                GuideTarget = "car",
                Hints = new[] { "The car is parked in front of the depot, a few steps away." },
                IsComplete = c => c.PlayerNear("car", 4.5f) || c.Car.HasDriver
            });
            m.Objectives.Add(StepEnterCar());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "t.drive",
                Text = "Drive across your bridge to the island",
                Voice = "t.drive",
                Checkpoint = true,
                GuideTarget = "route.island",
                Hints = new[] { "Follow the glowing guide lights. They follow the route you built." },
                OnBegin = c => c.Guide.ShowRoute("depot", "substation"),
                IsComplete = c => c.Car.CrossedBuiltBridge,
                OnComplete = c => { c.Guide.Hide(); c.Dialogue.Play("e1.crossed"); c.Nuri.Celebrate(); }
            });
            return m;
        }

        // ---------------------------------------------------------------- Episode 2
        static MissionDefinition BuildEpisode2()
        {
            var m = new MissionDefinition
            {
                Id = Episode2,
                Episode = 2,
                Title = "The Courier Run",
                Subtitle = "Episode 2",
                Briefing = "Carry a power cell across the causeway and wake the airfield.",
                StormSeconds = 300f,
                Start = StartLocation.StreetDepot,
                ReturnKiosk = "kiosk.A",
                ActiveSockets = new[] { "bridge_west", "bridge_east", "harbour_corner" },
                UseCampaignRoute = true,
                Inventory = new List<PieceDef>
                {
                    P("piece.bridge", ModuleType.Bridge),
                    P("piece.corner", ModuleType.Corner),
                    P("piece.straight", ModuleType.Straight)
                },
                IntroVoice = new[] { "e2.brief" },
                MedalRulesText = "Gold: 40% storm time left, no retries, at most 1 hint. Silver: 15% time left. Bronze: complete."
            };
            m.MedalFor = r => MedalFor(r, false);

            m.Objectives.Add(StepLoadCell());
            m.Objectives.Add(StepEnterCar());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e2.drive",
                Text = "Drive the cell to the airfield substation",
                Voice = "e2.drive",
                Checkpoint = true,
                GuideTarget = "substation.park",
                OnBegin = c => c.Guide.ShowRoute("depot", "substation"),
                Hints = new[] { "If the road is broken, fold at the depot station and rebuild it." },
                IsComplete = c => c.Car.DistanceTo("substation.park") < 9f
            });
            m.Objectives.Add(StepDeliver());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e2.convoy",
                Text = "Watch the convoy set off",
                Voice = "e2.convoy",
                OnBegin = c => { c.Guide.Hide(); c.Convoy.Depart(); c.Nuri.Celebrate(); },
                IsComplete = c => c.ObjectiveTime > 7f
            });
            return m;
        }

        // ---------------------------------------------------------------- Episode 3
        static MissionDefinition BuildEpisode3()
        {
            var m = new MissionDefinition
            {
                Id = Episode3,
                Episode = 3,
                Title = "The Last Flight",
                Subtitle = "Episode 3",
                Briefing = "Open the terminal road, light the runway and send the last flight.",
                StormSeconds = 330f,
                Start = StartLocation.StreetAirfield,
                ReturnKiosk = "kiosk.B",
                ActiveSockets = new[] { "terminal_link" },
                UseCampaignRoute = true,
                InitialFlags = new[] { Flags.SubstationPowered },
                Inventory = new List<PieceDef>
                {
                    P("piece.link.tee", ModuleType.Tee),
                    P("piece.link.corner", ModuleType.Corner),
                    P("piece.link.straight", ModuleType.Straight)
                },
                IntroVoice = new[] { "e3.brief" },
                MedalRulesText = "Gold: 40% storm time left, at most 2 rejected placements and 1 hint, no retries. Silver: 15% time left. Bronze: complete."
            };
            m.MedalFor = r => MedalFor(r, false);

            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.fold",
                TextVR = "Fold at the airfield Fold Station (X)",
                TextDesktop = "Fold at the airfield Fold Station (Q)",
                Voice = "e3.fold",
                GuideTarget = "kiosk.B",
                Checkpoint = true,
                IsComplete = c => c.Fold.InAtelier
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.link",
                Text = "Repair the terminal access link",
                Voice = "e3.link",
                GuideTarget = "socket.terminal_link",
                Hints = new[]
                {
                    "The terminal road runs straight north from the island road.",
                    "Only one of the three pieces fits without pointing into a building."
                },
                IsComplete = c => c.RouteToTerminal
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.unfold",
                TextVR = "Fold back down to the airfield (X)",
                TextDesktop = "Fold back down to the airfield (Q)",
                Voice = null,
                GuideTarget = "plinth",
                IsComplete = c => c.Fold.InStreet,
                OnComplete = c => c.Convoy.Depart()
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.beacons",
                Text = "Restore the runway beacons",
                Voice = "e3.beacons",
                Checkpoint = true,
                GuideTarget = "beacon.next",
                Progress = c => $"{c.Beacons.LitCount}/{c.Beacons.Total}",
                Hints = new[] { "The three switches stand along the runway edge. You can drive along the apron." },
                IsComplete = c => c.Beacons.AllLit
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.convoy",
                Text = "Wait for the convoy to reach the terminal",
                GuideTarget = "terminal.stop",
                IsComplete = c => c.Convoy.Arrived,
                OnComplete = c => c.Dialogue.Play("e3.convoy_arrived")
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.clear",
                Text = "Pull the departure lever at the tower",
                Voice = "e3.clear",
                GuideTarget = "lever.departure",
                IsComplete = c => c.City.GetFlag(Flags.DepartureCleared)
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.takeoff",
                Text = "Watch the last flight depart",
                Voice = "e3.takeoff",
                GuideTarget = "aircraft",
                IsComplete = c => c.Aircraft.State == AircraftState.Departed,
                OnComplete = c => { c.Dialogue.Play("e3.end"); c.Nuri.Celebrate(); }
            });
            return m;
        }

        // ---------------------------------------------------------------- Demo (3 minutes)
        static MissionDefinition BuildDemo()
        {
            var m = new MissionDefinition
            {
                Id = Demo,
                Episode = 0,
                IsDemo = true,
                Title = "The Last Flight",
                Subtitle = "Three-minute demo",
                Briefing = "One bridge, one power cell, one last flight.",
                StormSeconds = 360f,
                Start = StartLocation.Atelier,
                ReturnKiosk = "kiosk.A",
                ActiveSockets = new[] { "bridge_east" },
                Presets = new Dictionary<string, Placement>
                {
                    ["harbour_corner"] = new Placement { PieceId = "fixed.harbour", Type = ModuleType.Corner, Rotation = 1, Locked = true },
                    ["terminal_link"] = new Placement { PieceId = "fixed.terminal", Type = ModuleType.Straight, Rotation = 0, Locked = true }
                },
                Inventory = new List<PieceDef> { P("piece.bridge", ModuleType.Bridge) },
                ConvoyAtTerminal = true,
                IntroVoice = new[] { "d.welcome" },
                MedalRulesText = "Demo runs are not medalled for the campaign; time left is shown."
            };
            m.MedalFor = r => MedalFor(r, false);

            m.Objectives.Add(StepGrab("piece.bridge"));
            m.Objectives.Add(StepPlace());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "d.route",
                Text = "Connect the Depot to the island",
                GuideTarget = "socket.bridge_east",
                Hints = new[] { "The bridge runs north to south. Turn it until both ends meet the road." },
                IsComplete = c => c.RouteDepotToIsland,
                OnComplete = c => c.Dialogue.Play("e1.route_east")
            });
            m.Objectives.Add(StepFold("Fold down into the street"));
            m.Objectives.Add(StepLoadCell());
            m.Objectives.Add(StepEnterCar());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "t.drive",
                Text = "Drive the cell to the substation",
                Voice = "t.drive",
                Checkpoint = true,
                GuideTarget = "substation.park",
                OnBegin = c => c.Guide.ShowRoute("depot", "substation"),
                IsComplete = c => c.Car.DistanceTo("substation.park") < 9f
            });
            m.Objectives.Add(StepDeliver());
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "d.beacons",
                Text = "Flip the beacon switch beside the substation",
                Voice = "d.beacons",
                GuideTarget = "switch.demo",
                OnBegin = c => c.Guide.Hide(),
                IsComplete = c => c.Beacons.AllLit
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "d.clear",
                Text = "Pull the departure lever at the tower",
                Voice = "d.clear",
                GuideTarget = "lever.departure",
                IsComplete = c => c.City.GetFlag(Flags.DepartureCleared)
            });
            m.Objectives.Add(new ObjectiveDef
            {
                Id = "e3.takeoff",
                Text = "Watch the last flight depart",
                Voice = "e3.takeoff",
                GuideTarget = "aircraft",
                IsComplete = c => c.Aircraft.State == AircraftState.Departed,
                OnComplete = c => { c.Dialogue.Play("e3.end"); c.Nuri.Celebrate(); }
            });
            return m;
        }
    }

    /// <summary>CityState flag keys.</summary>
    public static class Flags
    {
        public const string SubstationPowered = "power.substation";
        public const string DepartureCleared = "departure.cleared";
        public const string ConvoyArrived = "convoy.arrived";
        public const string BeaconPrefix = "beacon.";
        public const string CarUnlocked = "car.unlocked";
    }
}
