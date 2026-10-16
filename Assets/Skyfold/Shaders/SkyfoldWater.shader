Shader "Skyfold/Water"
{
    Properties
    {
        _DeepColor ("Deep", Color) = (0.03, 0.29, 0.33, 1)
        _ShallowColor ("Shallow", Color) = (0.12, 0.56, 0.56, 1)
        _SkyColor ("Sky Reflection", Color) = (0.86, 0.82, 0.74, 1)
        _WaveHeight ("Wave Height", Float) = 0.12
        _WaveScale ("Wave Scale", Float) = 0.08
        _WaveSpeed ("Wave Speed", Float) = 0.6
        _RippleScale ("Ripple Scale", Float) = 0.45
        _RippleStrength ("Ripple Strength", Range(0, 1)) = 0.35
        _Gloss ("Gloss", Range(0, 1)) = 0.9
        _Storm ("Storm", Range(0, 1)) = 0
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry+10" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        CBUFFER_START(UnityPerMaterial)
            half4 _DeepColor;
            half4 _ShallowColor;
            half4 _SkyColor;
            float _WaveHeight;
            float _WaveScale;
            float _WaveSpeed;
            float _RippleScale;
            half _RippleStrength;
            half _Gloss;
            half _Storm;
        CBUFFER_END

        float3 WaveOffset(float3 ws, out float3 normalWS)
        {
            float t = _Time.y * _WaveSpeed * (1.0 + _Storm * 0.8);
            float h = _WaveHeight * (1.0 + _Storm * 2.5);
            float2 p = ws.xz * _WaveScale;
            float a1 = p.x * 0.9 + p.y * 0.4 + t;
            float a2 = p.x * -0.3 + p.y * 1.1 + t * 1.3;
            float a3 = p.x * 1.7 - p.y * 0.8 + t * 0.7;
            float y = h * (sin(a1) * 0.55 + sin(a2) * 0.35 + sin(a3) * 0.18);
            float dx = h * _WaveScale * (cos(a1) * 0.55 * 0.9 + cos(a2) * 0.35 * -0.3 + cos(a3) * 0.18 * 1.7);
            float dz = h * _WaveScale * (cos(a1) * 0.55 * 0.4 + cos(a2) * 0.35 * 1.1 + cos(a3) * 0.18 * -0.8);
            normalWS = normalize(float3(-dx, 1.0, -dz));
            return float3(0, y, 0);
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                half fogFactor : TEXCOORD2;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings vert (Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 n;
                ws += WaveOffset(ws, n);
                o.positionWS = ws;
                o.normalWS = n;
                o.positionCS = TransformWorldToHClip(ws);
                o.fogFactor = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float t = _Time.y * _WaveSpeed;
                float2 q = i.positionWS.xz * _RippleScale;
                float3 ripple = float3(
                    sin(q.x * 1.3 + t * 2.1) * 0.5 + sin(q.y * 2.7 - t * 1.7) * 0.3 + sin((q.x + q.y) * 3.1 + t * 2.9) * 0.2,
                    0,
                    cos(q.y * 1.1 - t * 1.9) * 0.5 + cos(q.x * 2.3 + t * 1.3) * 0.3 + cos((q.x - q.y) * 2.9 - t * 2.4) * 0.2);
                float3 n = normalize(i.normalWS + ripple * _RippleStrength * 0.35);
                float3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                Light mainLight = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                half shadow = lerp(0.55h, 1.0h, mainLight.shadowAttenuation);

                half fres = pow(1.0h - saturate(dot(n, v)), 4.0h);
                half3 deep = lerp(_DeepColor.rgb, _DeepColor.rgb * 0.55h, _Storm);
                half3 water = lerp(deep, _ShallowColor.rgb, saturate(n.y * 0.5h + 0.25h + ripple.x * 0.05h));
                half3 sky = lerp(_SkyColor.rgb, half3(0.38h, 0.4h, 0.5h), _Storm);
                half3 color = lerp(water, sky, fres * 0.65h);
                color *= (SampleSH(float3(0, 1, 0)) * 0.6h + mainLight.color * 0.45h) * shadow;

                float3 h = normalize(mainLight.direction + v);
                half spec = pow(saturate(dot(n, h)), 220.0h * _Gloss + 20.0h) * 2.2h * (1.0h - _Storm * 0.7h);
                color += mainLight.color * spec * mainLight.shadowAttenuation;
                color = MixFog(color, i.fogFactor);
                return half4(color, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R

            HLSLPROGRAM
            #pragma vertex DepthVert
            #pragma fragment DepthFrag
            #pragma multi_compile_instancing
            struct Attributes { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; UNITY_VERTEX_OUTPUT_STEREO };
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
    }
    FallBack Off
}
