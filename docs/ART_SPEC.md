# SKYFOLD Art and Asset Spec

Shared contract for every 3D and audio asset. Unity is the integration owner: asset makers write files only to the folders below and never run Unity or git.

## Look

Premium stylized 3D: tactile miniature-city craftsmanship, warm coastal futurism. Nacre Bay is an **original fictional** coastal city. Do not copy real landmarks, brands or franchises, and do not build a digital twin of any real city.

- Chunky, readable silhouettes with slightly exaggerated proportions. Beveled edges everywhere: architecture 0.04–0.08 m, props 0.01–0.02 m, characters and vehicles 0.005–0.02 m. No sharp CG cubes.
- Architecture language: cubic pearl and sandstone volumes, arched loggias, shaded courtyards, stepped parapets, slender wind-tower-like vents, small domes, pergolas with shade sails, simple geometric lattice screens, planters and palms. Futurism shows up as teal glass bands, rounded corners, brass trims and soft teal light strips.
- Avoid noisy micro-detail, text, logos, photoreal textures and generic blue holograms.

## Palette (exact material names; Unity remaps them by name)

| Material | Hex | Use |
| --- | --- | --- |
| SKY_Pearl | #F4EFE6 | Main structure, trims |
| SKY_Ivory | #EFE6D2 | NURI shell, gloves, premium panels |
| SKY_Sandstone | #D9B98C | Walls, paving |
| SKY_SandstoneDeep | #C49A6C | Bases, steps, shadows in stone |
| SKY_Terracotta | #C8754F | Roof tiles, planters (sparingly) |
| SKY_Teal | #0F6F73 | Technology, accents, car stripe |
| SKY_TealLight | #3FA7A3 | Glass bands, secondary tech |
| SKY_TealGlow | #35E0D0 | Emissive tech lights, NURI lens |
| SKY_Coral | #F2714B | Hazards, barriers, awnings |
| SKY_Gold | #D9A441 | Rewards only (route light, medals) |
| SKY_Brass | #B8893B | Metal trims, NURI wing edges, lamps |
| SKY_Ink | #22333B | Dark details, tyres, window frames |
| SKY_Glass | #6FB7C4 | Glass (Unity makes it translucent) |
| SKY_Road | #3E4A52 | Asphalt |
| SKY_RoadLine | #F4EFE6 | Lane markings |
| SKY_Kerb | #CDBFA9 | Kerbs and sidewalks |
| SKY_Wood | #9A6B45 | Pergolas, benches, boats |
| SKY_PalmTrunk | #8B6B4A | Palm trunks |
| SKY_PalmLeaf | #5E8C4A | Palm fronds, shrubs |
| SKY_Flower | #E0557A | Bougainvillea accents |
| SKY_Fabric | #F7F1E6 | Shade sails |
| SKY_Metal | #AEB6BA | Plain metal |
| SKY_Rubber | #2B2F33 | Tyres |
| SKY_Light | #FFD9A0 | Warm emissive lamps and windows |

Assign these material names in Blender. Viewport colours are only for preview renders.

## Units, axes, pivots

- Meters, Blender unit scale 1.0, everything modeled at real size.
- **Directions.** Unity north (+Z) is Blender **-Y**. Unity east (+X) is Blender **-X**. Up is +Z in Blender and +Y in Unity. Modeling a vehicle or character facing Blender -Y (the default "front" view) makes it face Unity forward.
- **FBX export** (Blender 5.2): `bpy.ops.export_scene.fbx(filepath=..., use_selection=True, object_types={'EMPTY','MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type='FACE', add_leaf_bones=False, use_armature_deform_only=True, colors_type='SRGB', path_mode='AUTO', embed_textures=False)`. Apply all transforms before export.
- **Pivots**: road, bridge, quay and building modules sit at the bottom center of their 16 m x 16 m cell footprint (ground = Z 0). Vehicles sit on the ground, centered between the axles. Parts that rotate pivot at their hinge or hub.
- **Vertex colour AO**: after bevels are applied, add a colour attribute named `Col` holding a soft dirty-vertex-colour / AO bake (white = unoccluded). Unity multiplies albedo by it.
- **Empties** are named `ANCHOR_*`, `SOCKET_*` or `LIGHT_*` and mark gameplay points. Keep them in the FBX.
- Smooth shading with sharp edges, or auto-smooth equivalent. No n-gons that break FBX triangulation. Tri budgets (raised in the detail pass; the laptop renders the demo at roughly 900 fps, so geometry is not the bottleneck, but VR draws every mesh twice: once in the street and once in the 1:160 miniature): building up to 16k (hangar and terminal up to 20k), road and ground tiles under 2k, quays under 4k, bridges under 9k, palm under 4.5k, shrub under 2.5k, prop under 1.5k (street lamp under 2k), Atelier pieces under 12k, courier car under 24k, convoy shuttle under 18k, city car under 12k, aircraft under 40k, power cell under 2.5k, NURI under 16k, each glove under 14k, passenger under 7k. Spend triangles where they read: silhouettes, openings, trims and moving parts, not hidden faces.

## City grid (for sizing)

- One cell is 16 m x 16 m. Roads are 8 m of asphalt centered in the cell, with 0.15 m raised kerbs and sidewalks out to the cell edge on non-road sides.
- A road opening on a cell edge means 8 m of asphalt reaching that edge, with sidewalks on either side.
- Road surface is at Z 0. Water surface is at Z -1.2, seabed at Z -4. Bridge decks are at Z 0 and match the road profile.
- Building footprints are at most 12 m x 12 m, centered in the cell, and 6–20 m tall.
- The miniature reuses the same meshes at 1:160 scale, so silhouettes must read when 10 cm wide.

## Output folders (inside `C:\UnityProjects\SKYFOLD`)

| What | Where |
| --- | --- |
| FBX models | `Assets/Skyfold/Art/Models/<Category>/<name>.fbx` (Category: Roads, Buildings, Props, Nature, Vehicles, Characters, Atelier, Sky) |
| Blender build scripts | `tools/blender/` (reproducible: `blender -b -P tools/blender/<script>.py`) |
| Optional .blend sources | `source-art/blender/` (keep each file under 50 MB) |
| Preview renders | `source-art/renders/<name>.png` plus a contact sheet |
| Model manifest | `source-art/models_manifest_<stream>.json` (file, objects, empties with positions in Unity axes, bounds, tri counts) |
| Audio | `Assets/Skyfold/Audio/{VO,Music,SFX,Ambience}/` |
| Audio tools | `tools/audio/` |
| Manifest entries | `docs/manifest/<stream>.md` (filename, source/provider, licence, retrieval date, modifications, AI status, prompt/script, where used) |

Never download assets of unclear licence. Original procedural work is preferred. The `kanban-motion` skill's bundled SFX are Kenney CC0. Record every external source.
