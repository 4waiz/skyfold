using UnityEditor;
using UnityEngine;

namespace Skyfold.EditorTools
{
    /// <summary>Consistent import settings for SKYFOLD models and audio.</summary>
    public sealed class SkyfoldAssetPostprocessor : AssetPostprocessor
    {
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
