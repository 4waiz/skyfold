using UnityEditor;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>Consistent import settings for SKYFOLD models, audio and images.</summary>
    public sealed class SkyfoldAssetPostprocessor : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            // ChatGPT images and their derivatives. Only noor_badge.png is referenced by the scene (the HUD
            // subtitle badge); the rest are references that never reach the build.
            if (!assetPath.StartsWith("Assets/Skyfold/Art/Images/")) return;
            var ti = (TextureImporter)assetImporter;
            ti.textureType = TextureImporterType.Sprite;
            ti.spriteImportMode = SpriteImportMode.Single;
            ti.alphaIsTransparency = true;
            ti.mipmapEnabled = true; // the 256 px badge is drawn at about 96-140 px
            ti.filterMode = FilterMode.Trilinear;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
        }

        void OnPreprocessModel()
        {
            if (!assetPath.StartsWith("Assets/Skyfold/Art/Models")) return;
            var mi = (ModelImporter)assetImporter;
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.importBlendShapes = false;
            mi.importVisibility = false;
            mi.importCameras = false;
            mi.importLights = false;
            mi.animationType = ModelImporterAnimationType.None;
            mi.importAnimation = false;
            mi.isReadable = true;
            mi.meshCompression = ModelImporterMeshCompression.Off;
            mi.optimizeMeshPolygons = true;
            mi.optimizeMeshVertices = true;
            mi.importNormals = ModelImporterNormals.Import;
            mi.importTangents = ModelImporterTangents.None;
            mi.addCollider = false;
            mi.generateSecondaryUV = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
        }

        void OnPreprocessAudio()
        {
            if (!assetPath.StartsWith("Assets/Skyfold/Audio")) return;
            var ai = (AudioImporter)assetImporter;
            var s = ai.defaultSampleSettings;
            bool music = assetPath.Contains("/Music/");
            bool amb = assetPath.Contains("/Ambience/");
            bool vo = assetPath.Contains("/VO/");
            s.compressionFormat = AudioCompressionFormat.Vorbis;
            s.quality = music || amb ? 0.62f : vo ? 0.72f : 0.8f;
            s.loadType = music || amb ? AudioClipLoadType.Streaming : vo ? AudioClipLoadType.CompressedInMemory : AudioClipLoadType.DecompressOnLoad;
            s.preloadAudioData = !(music || amb);
            ai.defaultSampleSettings = s;
            ai.forceToMono = !(music || amb);
            ai.loadInBackground = music || amb;
        }
    }
}
