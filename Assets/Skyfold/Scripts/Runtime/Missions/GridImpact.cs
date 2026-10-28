using System;

namespace Skyfold
{
    /// <summary>
    /// The Nacre Bay clean grid: the share of the city's power that comes from renewables. It is worked out
    /// from CityState facts (never timers), so every repair the player makes brings another source online.
    /// These are game values for the story, not real-world measurements.
    /// </summary>
    public static class GridImpact
    {
        public sealed class Source
        {
            public string Label;
            public int Share;
            public Func<MissionContext, bool> Online;
        }

        /// <summary>Rooftop solar already feeds the mainland before the player repairs anything.</summary>
        public const int BaseShare = 30;

        public static readonly Source[] Sources =
        {
            new Source { Label = "Wind and solar power reach the island", Share = 30, Online = c => c.RouteDepotToIsland },
            new Source { Label = "Hydrogen microgrid online", Share = 20, Online = c => c.City.GetFlag(Flags.SubstationPowered) },
            new Source { Label = "Solar runway lights on", Share = 10, Online = c => c.Beacons != null && c.Beacons.AllLit },
            new Source { Label = "Zero-emission flight cleared", Share = 10, Online = c => c.City.GetFlag(Flags.DepartureCleared) },
        };

        static bool IsOnline(Source s, MissionContext c)
        {
            if (c == null || c.City == null) return false;
            try { return s.Online(c); }
            catch (NullReferenceException) { return false; }
        }

        /// <summary>Bit i is set when Sources[i] is online.</summary>
        public static int Mask(MissionContext c)
        {
            int m = 0;
            for (int i = 0; i < Sources.Length; i++) if (IsOnline(Sources[i], c)) m |= 1 << i;
            return m;
        }

        public static int Share(int mask)
        {
            int share = BaseShare;
            for (int i = 0; i < Sources.Length; i++) if ((mask & (1 << i)) != 0) share += Sources[i].Share;
            return share;
        }

        public static int Share(MissionContext c) => Share(Mask(c));

        /// <summary>The label of the newest source in `now` that was not in `before`, or null.</summary>
        public static string NewSource(int before, int now)
        {
            for (int i = Sources.Length - 1; i >= 0; i--)
                if ((now & (1 << i)) != 0 && (before & (1 << i)) == 0) return Sources[i].Label;
            return null;
        }

        /// <summary>One plain-language energy fact per episode for the results screen.</summary>
        public static string FactFor(int episode)
        {
            switch (episode)
            {
                case 1: return "Power cables often travel along bridges and under the sea, linking wind and solar farms to the cities that need the electricity.";
                case 2: return "Green hydrogen is made by splitting water with renewable electricity. The only by-product is oxygen.";
                case 3: return "A hydrogen fuel cell turns hydrogen into electricity, and the only thing it gives off is water.";
                default: return "Grid batteries store solar and wind power, so the lights stay on after sunset and when the wind drops.";
            }
        }
    }
}
