Shader "Skyfold/StylizedLit"
{
    Properties
    {
        [MainColor] _BaseColor ("Base Color", Color) = (1, 1, 1, 1)
        [MainTexture] _BaseMap ("Base Map", 2D) = "white" {}
        _Smoothness ("Smoothness", Range(0, 1)) = 0.25
        _Metallic ("Metallic", Range(0, 1)) = 0
        _EnvStrength ("Sky Reflection", Range(0, 2)) = 1
        _DetailStrength ("Surface Variation", Range(0, 0.3)) = 0
        _DetailScale ("Surface Variation Scale (per m)", Float) = 0.9
        _AOStrength ("Vertex AO Strength", Range(0, 1)) = 0.85
        [HDR] _EmissionColor ("Emission", Color) = (0, 0, 0, 1)
        _Highlight ("Highlight", Range(0, 1)) = 0
        _HighlightColor ("Highlight Color", Color) = (0.21, 0.88, 0.82, 1)
        _Wrap ("Light Wrap", Range(0, 1)) = 0.35
        _ShadowTint ("Shadow Tint", Color) = (0.55, 0.62, 0.78, 1)
        _SrcBlend ("Src Blend", Float) = 1
        _DstBlend ("Dst Blend", Float) = 0
        _ZWrite ("ZWrite", Float) = 1
        _Cull ("Cull", Float) = 2
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            half _Smoothness;
            half _Metallic;
            half _EnvStrength;
            half _DetailStrength;
            float _DetailScale;
            half _AOStrength;
            half4 _EmissionColor;
            half _Highlight;
            half4 _HighlightColor;
            half _Wrap;
            half4 _ShadowTint;
            half _SrcBlend;
            half _DstBlend;
            half _ZWrite;
            half _Cull;
        CBUFFER_END
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Blend [_SrcBlend] [_DstBlend]
            ZWrite [_ZWrite]
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            // Forward+ (the PC renderer's path): lights come from the cluster loop, not per-object lists.
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            // The renderer's SSAO feature: contact shadows in corners, under ledges and around props.
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                half4 color : COLOR;
                float2 uv : TEXCOORD2;
                half fogFactor : TEXCOORD3;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            // Cheap world-space value noise (two octaves) for gentle stone/asphalt mottling. Low contrast
            // and low frequency on purpose: the art style avoids noisy micro-detail.
            float Hash31(float3 p)
            {
                p = frac(p * 0.3183099 + 0.1);
                p *= 17.0;
                return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
            }

            float ValueNoise(float3 x)
            {
                float3 i = floor(x);
                float3 f = frac(x);
                f = f * f * (3.0 - 2.0 * f);
                float n000 = Hash31(i), n100 = Hash31(i + float3(1, 0, 0));
                float n010 = Hash31(i + float3(0, 1, 0)), n110 = Hash31(i + float3(1, 1, 0));
                float n001 = Hash31(i + float3(0, 0, 1)), n101 = Hash31(i + float3(1, 0, 1));
                float n011 = Hash31(i + float3(0, 1, 1)), n111 = Hash31(i + float3(1, 1, 1));
                return lerp(lerp(lerp(n000, n100, f.x), lerp(n010, n110, f.x), f.y),
                            lerp(lerp(n001, n101, f.x), lerp(n011, n111, f.x), f.y), f.z);
            }

            Varyings vert (Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color = v.color;
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                o.fogFactor = ComputeFogFactor(p.positionCS.z);
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);

                half4 tex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv);
                half3 albedo = tex.rgb * _BaseColor.rgb;
                UNITY_BRANCH
                if (_DetailStrength > 0.001h)
                {
                    float3 q = i.positionWS * _DetailScale;
                    half grain = (half)(ValueNoise(q) * 0.65 + ValueNoise(q * 3.1 + 7.3) * 0.35);
                    albedo *= 1.0h + (grain * 2.0h - 1.0h) * _DetailStrength;
                }
                half ao = lerp(1.0h, i.color.r, _AOStrength);

                float3 n = normalize(i.normalWS);
                float3 viewDir = GetWorldSpaceNormalizeViewDir(i.positionWS);
                float2 screenUV = GetNormalizedScreenSpaceUV(i.positionCS);
                half ssaoIndirect = 1.0h, ssaoDirect = 1.0h;
                #if defined(_SCREEN_SPACE_OCCLUSION)
                    AmbientOcclusionFactor aoFactor = GetScreenSpaceAmbientOcclusion(screenUV);
                    ssaoIndirect = aoFactor.indirectAmbientOcclusion;
                    ssaoDirect = aoFactor.directAmbientOcclusion;
                #endif

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light mainLight = GetMainLight(shadowCoord);

                half ndl = dot(n, mainLight.direction);
                half wrap = saturate((ndl + _Wrap) / (1.0h + _Wrap));
                half shadow = mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half lit = wrap * shadow * ssaoDirect;

                // Metals keep some diffuse so brass never goes black in shade (stylized, not strict PBR).
                half metallic = _Metallic;
                half3 diffuseColor = albedo * (1.0h - metallic * 0.65h);

                half3 ambient = SampleSH(n) * ssaoIndirect;
                half3 shadowSide = lerp(_ShadowTint.rgb, half3(1, 1, 1), lit);
                half3 color = diffuseColor * (mainLight.color * lit + ambient * shadowSide);

                // Sun highlight: a soft white sheen on dielectrics, a tinted, tighter glint on metals.
                float3 h = normalize(mainLight.direction + viewDir);
                half specPow = exp2(10.0h * _Smoothness + 1.0h);
                half3 specColor = lerp(half3(0.45h, 0.45h, 0.45h) * _Smoothness, albedo * (0.6h + 1.4h * _Smoothness), metallic);
                color += mainLight.color * specColor * pow(saturate(dot(n, h)), specPow) * shadow * ssaoDirect * saturate(ndl * 4.0h);

                // Sky reflection from the ambient probe in the reflected direction (no baked cubemap needed):
                // glass and glossy paint pick up the sky at grazing angles, metals reflect it tinted.
                half ndv = saturate(dot(n, viewDir));
                half fresnel = pow(1.0h - ndv, 4.0h);
                half3 env = SampleSH(reflect(-viewDir, n));
                half3 envTint = lerp(half3(0.04h, 0.04h, 0.04h) + 0.5h * fresnel, albedo, metallic);
                color += env * envTint * (_Smoothness * _Smoothness) * _EnvStrength * ssaoIndirect;

                #if defined(_ADDITIONAL_LIGHTS)
                // Same loop structure as URP Lit, so Forward and Forward+ both get the right lights.
                InputData inputData = (InputData)0;
                inputData.positionWS = i.positionWS;
                inputData.normalizedScreenSpaceUV = screenUV;
                uint pixelLightCount = GetAdditionalLightsCount();
                #if USE_CLUSTER_LIGHT_LOOP
                [loop] for (uint lightIndex = 0; lightIndex < min(URP_FP_DIRECTIONAL_LIGHTS_COUNT, MAX_VISIBLE_LIGHTS); lightIndex++)
                {
                    Light l = GetAdditionalLight(lightIndex, i.positionWS);
                    color += diffuseColor * l.color * l.distanceAttenuation * l.shadowAttenuation * saturate(dot(n, l.direction) * 0.7h + 0.3h);
                }
                #endif
                LIGHT_LOOP_BEGIN(pixelLightCount)
                    Light l = GetAdditionalLight(lightIndex, i.positionWS);
                    color += diffuseColor * l.color * l.distanceAttenuation * l.shadowAttenuation * saturate(dot(n, l.direction) * 0.7h + 0.3h);
                LIGHT_LOOP_END
                #endif

                color *= ao;
                half rim = pow(1.0h - ndv, 2.5h);
                color += _HighlightColor.rgb * _Highlight * (0.25h + rim * 1.5h);
                color += _EmissionColor.rgb;
                color = MixFog(color, i.fogFactor);
                return half4(color, _BaseColor.a * tex.a);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
            };

            Varyings ShadowVert (Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 posWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 nWS = TransformObjectToWorldNormal(v.normalOS);
                #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                    float3 lightDir = normalize(_LightPosition - posWS);
                #else
                    float3 lightDir = _LightDirection;
                #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(posWS, nWS, lightDir));
                #if UNITY_REVERSED_Z
                    cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
                #else
                    cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                o.positionCS = cs;
                return o;
            }

            half4 ShadowFrag (Varyings i) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex DepthVert
            #pragma fragment DepthFrag
            #pragma multi_compile_instancing

            struct Attributes
            {
                float4 positionOS : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings DepthVert (Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                return o;
            }

            half DepthFrag (Varyings i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }

        // Depth + world normals for the SSAO renderer feature (its "Depth Normals" source).
        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex DepthNormalsVert
            #pragma fragment DepthNormalsFrag
            #pragma multi_compile_instancing
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings DepthNormalsVert (Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }

            half4 DepthNormalsFrag (Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                #if defined(_GBUFFER_NORMALS_OCT)
                    float3 nWS = normalize(i.normalWS);
                    float2 oct = PackNormalOctQuadEncode(nWS);
                    half3 packed = PackFloat2To888(saturate(oct * 0.5 + 0.5));
                    return half4(packed, 0.0);
                #else
                    return half4(NormalizeNormalPerPixel(i.normalWS), 0.0);
                #endif
            }
            ENDHLSL
        }
    }
    FallBack Off
}
