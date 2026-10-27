using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace Skyfold.EditorTools
{
    public static partial class SceneBuilder
    {
        static T Sys<T>(Ctx c, string name) where T : Component => Child(c.Systems, name).AddComponent<T>();

        static void BuildSystems(Ctx c, AudioLibrary lib)
        {
            // UI theme first (fonts) so every screen uses them.
            var theme = Sys<UITheme>(c, "UI Theme");
            theme.heading = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(FontSetup.HeadingAsset);
            theme.body = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(FontSetup.BodyAsset);
            // Noor's radio badge: ChatGPT portrait cropped into a circle by tools/images/make_image_derivatives.py.
            var portrait = AssetDatabase.LoadAssetAtPath<Sprite>("Assets/Skyfold/Art/Images/noor_badge.png");
            if (portrait == null) Debug.LogWarning("[SKYFOLD] Noor badge sprite missing; the HUD falls back to the radio glyph.");
            theme.noorPortrait = portrait;

            Sys<XRInteractionManager>(c, "XR Interaction Manager");
            var esGo = Child(c.Systems, "EventSystem");
            esGo.AddComponent<EventSystem>();
            var desktopUI = esGo.AddComponent<InputSystemUIInputModule>();
            desktopUI.AssignDefaultActions();
            var xrUI = esGo.AddComponent<XRUIInputModule>();
            xrUI.enabled = false;

            var input = Sys<InputRouter>(c, "Input Router");
            var xr = Sys<XRBootstrap>(c, "XR Bootstrap");
            var audio = Sys<AudioDirector>(c, "Audio Director");
            audio.library = lib;
            var dialogue = Sys<DialogueDirector>(c, "Dialogue Director");
            var fader = Sys<ScreenFader>(c, "Screen Fader");
            fader.fadeShader = Shader.Find("Skyfold/Fade");

            var rigs = Sys<PlayerRigs>(c, "Player Rigs");
            rigs.desktop = c.Desktop;
            rigs.vr = c.VR;

            var fold = Sys<FoldController>(c, "Fold Controller");
            var atelierAnchor = c.Layout.GetAnchor("atelier.player");
            fold.atelierAnchor = Child(c.Atelier, "Atelier Arrive", atelierAnchor.Position, atelierAnchor.Yaw).transform;
            fold.stations = c.Stations.ToArray();

            var tabletop = Sys<TabletopController>(c, "Tabletop Controller");
            tabletop.mini = c.Mini;
            tabletop.pieces = c.Pieces;
            var tdi = c.Desktop.GetComponent<TabletopDesktopInput>();
            tdi.controller = tabletop;

            var mirror = Sys<MiniatureMirror>(c, "Miniature Mirror");
            mirror.mini = c.Mini;
            mirror.pairs = c.MirrorPairs;
            BuildEnergyLab(c, mirror);

            var beacons = Sys<BeaconSystem>(c, "Beacon System");
            beacons.groups = c.BeaconGroups;
            beacons.switches = c.Switches;
            beacons.masterSwitch = c.MasterSwitch;

            var convoy = Sys<ConvoyDirector>(c, "Convoy Director");
            convoy.shuttles = c.Shuttles;
            var traffic = Sys<TrafficDirector>(c, "Traffic Director");
            traffic.cars = c.Traffic;

            var guide = Sys<RouteGuide>(c, "Route Guide");
            guide.markerMaterial = MaterialLibrary.Get("SKY_Guide");
            guide.miniLine = c.MiniLine;

            var storm = Sys<StormDirector>(c, "Storm Director");
            storm.sun = c.Sun;
            storm.sky = c.Sky;
            storm.stormFront = c.StormFront;
            storm.rain = c.Rain;
            storm.lightning = c.Lightning;

            var overlook = Sys<OverlookDirector>(c, "Overlook Director");
            overlook.overlooks = c.Overlooks.ToArray();

            c.Lever.aircraft = c.Aircraft;
            if (c.Substation != null)
            {
                c.Substation.islandLights = c.IslandLights;
                c.Substation.islandWindows = c.IslandWindows;
            }

            var missions = Sys<MissionDirector>(c, "Mission Director");
            var menu = Sys<MenuController>(c, "Menus");
            var hud = Sys<HUDController>(c, "HUD");
            hud.noorPortrait = portrait;
            hud.wristAnchorOverride = c.Atrium;
            var diag = Sys<InputDiagnostics>(c, "Input Diagnostics");
            var qa = Sys<QARunner>(c, "QA Runner");

            var root = Sys<GameRoot>(c, "Game Root");
            root.rigs = rigs;
            root.input = input;
            root.xr = xr;
            root.missions = missions;
            root.dialogue = dialogue;
            root.audioDirector = audio;
            root.fold = fold;
            root.tabletop = tabletop;
            root.car = c.Car;
            root.cell = c.Cell;
            root.beacons = beacons;
            root.convoy = convoy;
            root.aircraft = c.Aircraft;
            root.nuri = c.Nuri;
            root.guide = guide;
            root.substation = c.Substation;
            root.traffic = traffic;
            root.slots = c.Slots;
            root.menu = menu;
            root.hud = hud;
            root.fader = fader;
            root.diagnostics = diag;
            root.qa = qa;
        }
    }
}
