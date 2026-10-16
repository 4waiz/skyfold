Shader "Skyfold/Sky"
{
    Properties
    {
        _Zenith ("Zenith", Color) = (0.34, 0.58, 0.71, 1)
        _Horizon ("Horizon", Color) = (0.99, 0.84, 0.66, 1)
        _Haze ("Haze (low sky)", Color) = (0.8, 0.88, 0.92, 1)
        _Below ("Below Horizon", Color) = (0.62, 0.66, 0.66, 1)
        _SunColor ("Sun", Color) = (1, 0.86, 0.62, 1)
        _SunSize ("Sun Size", Range(0.001, 0.08)) = 0.028
        _SunGlow ("Sun Glow", Range(0, 4)) = 1.4
        _CloudColor ("Cloud", Color) = (1, 0.95, 0.88, 1)
        _CloudAmount ("Cloud Amount", Range(0, 1)) = 0.45
        _Storm ("Storm", Range(0, 1)) = 0
        _StormZenith ("Storm Zenith", Color) = (0.16, 0.18, 0.3, 1)
        _StormHorizon ("Storm Horizon", Color) = (0.6, 0.42, 0.42, 1)
    }

    SubShader
    {
        Tags { "Queue" = "Background" "RenderType" = "Background" "PreviewType" = "Skybox" "RenderPipeline" = "UniversalPipeline" }
        Cull Off
        ZWrite Off

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _Zenith, _Horizon, _Haze, _Below, _SunColor, _CloudColor, _StormZenith, _StormHorizon;
                half _SunSize, _SunGlow, _CloudAmount, _Storm;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; UNITY_VERTEX_OUTPUT_STEREO };

            Varyings vert (Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.dir = v.positionOS.xyz;
                return o;
            }

            float Hash(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
            float Noise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(Hash(i), Hash(i + float2(1, 0)), u.x), lerp(Hash(i + float2(0, 1)), Hash(i + float2(1, 1)), u.x), u.y);
            }

            half4 frag (Varyings i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float3 d = normalize(i.dir);
                half storm = _Storm;
                half3 zenith = lerp(_Zenith.rgb, _StormZenith.rgb, storm);
                half3 horizon = lerp(_Horizon.rgb, _StormHorizon.rgb, storm);
                half up = saturate(d.y);
                // Three stops (warm horizon, pale haze, deep zenith) so the warm-to-blue blend never turns grey.
                half3 haze = lerp(_Haze.rgb, lerp(_StormZenith.rgb, _StormHorizon.rgb, 0.5h), storm);
                half3 col = lerp(horizon, haze, smoothstep(0.0h, 0.16h, up));
                col = lerp(col, zenith, pow(saturate((up - 0.05h) / 0.75h), 0.65h));
                if (d.y < 0.0)
                {
                    half down = saturate(-d.y * 6.0h);
                    col = lerp(horizon, _Below.rgb * lerp(1.0h, 0.55h, storm), down);
                }

                float3 sunDir = _MainLightPosition.xyz;
                half sd = saturate(dot(d, sunDir));
                half disc = smoothstep(1.0h - _SunSize, 1.0h - _SunSize * 0.6h, sd);
                half glow = pow(sd, 8.0h) * 0.35h + pow(sd, 64.0h) * 0.6h;
                col += _SunColor.rgb * (disc * 3.0h + glow * _SunGlow) * (1.0h - storm * 0.85h);

                // Soft painterly cloud bands drifting slowly near the horizon.
                if (d.y > 0.0)
                {
                    float2 uv = d.xz / (d.y + 0.25) * 1.6 + float2(_Time.y * 0.004, _Time.y * 0.002);
                    float n = Noise(uv) * 0.6 + Noise(uv * 2.3) * 0.3 + Noise(uv * 5.1) * 0.1;
                    half amount = lerp(_CloudAmount, 0.85h, storm);
                    half c = smoothstep(1.0h - amount, 1.0h - amount + 0.14h, n) * smoothstep(0.02h, 0.2h, d.y) * (1.0h - smoothstep(0.6h, 0.95h, d.y));
                    // Lit tops, slightly shaded bellies: denser noise reads as the cloud's underside.
                    half shade = saturate((n - (1.0h - amount)) * 2.2h);
                    half3 cloud = lerp(_CloudColor.rgb, _CloudColor.rgb * half3(0.82h, 0.8h, 0.86h), shade);
                    cloud = lerp(cloud, half3(0.32h, 0.34h, 0.44h), storm) * (0.9h + 0.25h * sd);
                    col = lerp(col, cloud, c * 0.85h);
                }
                return half4(col, 1);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
