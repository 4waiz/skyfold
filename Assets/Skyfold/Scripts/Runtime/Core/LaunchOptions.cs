using System;
using System.Collections.Generic;
using System.Globalization;

namespace Skyfold
{
    public enum LaunchMode { Ask, Desktop, VR }

    /// <summary>
    /// SKYFOLD's own command-line arguments (these are not Unity flags):
    ///   --mode=desktop | --mode=vr      start directly in that mode (otherwise the launcher asks)
    ///   --demo                          open the three-minute demo mission
    ///   --episode=1|2|3                 jump to an episode
    ///   --windowed                      start in a window instead of borderless fullscreen
    ///   --diagnostics                   show the input diagnostics panel
    ///   --qa=&lt;scenario&gt;               run an automated QA scenario and quit
    ///   --qa-out=&lt;folder&gt;               where QA writes screenshots and reports
    /// </summary>
    public sealed class LaunchOptions
    {
        public LaunchMode Mode = LaunchMode.Ask;
        public bool Demo;
        public int Episode;
        public bool Windowed;
        public bool Diagnostics;
        public string QaScenario;
        public string QaOut;
        public readonly List<string> Unknown = new List<string>();

        public static LaunchOptions Current { get; private set; } = new LaunchOptions();

        public static LaunchOptions Parse(string[] args)
        {
            var o = new LaunchOptions();
            if (args == null) return o;
            foreach (var raw in args)
            {
                if (string.IsNullOrEmpty(raw) || !raw.StartsWith("--", StringComparison.Ordinal)) continue;
                string arg = raw.Substring(2);
                string key = arg, value = null;
                int eq = arg.IndexOf('=');
                if (eq >= 0) { key = arg.Substring(0, eq); value = arg.Substring(eq + 1).Trim('"'); }
                switch (key.ToLowerInvariant())
                {
                    case "mode":
                        if (string.Equals(value, "vr", StringComparison.OrdinalIgnoreCase)) o.Mode = LaunchMode.VR;
                        else if (string.Equals(value, "desktop", StringComparison.OrdinalIgnoreCase)) o.Mode = LaunchMode.Desktop;
                        break;
                    case "demo": o.Demo = true; break;
                    case "episode":
                        if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var ep)) o.Episode = Math.Max(0, Math.Min(3, ep));
                        break;
                    case "windowed": o.Windowed = true; break;
                    case "diagnostics": o.Diagnostics = true; break;
                    case "qa": o.QaScenario = value; break;
                    case "qa-out": o.QaOut = value; break;
                    default: o.Unknown.Add(raw); break;
                }
            }
            return o;
        }

        public static LaunchOptions Init()
        {
            Current = Parse(Environment.GetCommandLineArgs());
            return Current;
        }

        public override string ToString() =>
            $"mode={Mode} demo={Demo} episode={Episode} windowed={Windowed} diagnostics={Diagnostics} qa={QaScenario ?? "-"}";
    }
}
