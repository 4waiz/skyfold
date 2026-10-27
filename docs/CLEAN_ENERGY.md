# Clean Energy Challenge: design notes

A project by Awaiz Ahmed for ADIPEC 2026. Audience: high-school students and recent graduates. Length: about three minutes. Plays on the laptop or in VR (Quest 3 through Link).

## Flow and timing

| Step | What the player does | Typical | Hard cap |
| --- | --- | --- | --- |
| Welcome | Noor: "Three quick puzzles stand between this island and net zero." | 5 s | none (the first puzzle starts at once) |
| 1 · Power the city 24/7 | Drop 4 of 5 energy blocks into the grid | 25–45 s | help starts at 60 s |
| Fact card | Clean grid power from nuclear and solar | 6.5 s | |
| 2 · Capture the carbon | Turn pipe tiles until the CO₂ reaches the storage well | 20–40 s | help starts at 55 s |
| Fact card | Al Reyadah carbon capture | 6.5 s | |
| 3 · Blue carbon coast | Plant mangroves on glowing mudflats | 27 s (2 s countdown + 25 s round) | ends at 27 s |
| Fact card | 10 million mangroves | 6.5 s | |
| Finale | Score columns, rank, net zero 2045 | 7 s | |
| Results | Score per puzzle, best score, *Play again* | | back to the title after 90 s idle |

A player who solves nothing still finishes in about 3:20, because each puzzle solves itself step by step after its budget. A quick player finishes in about 2:00.

## The puzzles

**1 · Power the city 24/7** (`EnergyMixGame`). Four grid slots, five blocks. The city needs 3 units by day and 3 at night, with zero CO₂.

| Block | Day | Night | CO₂ |
| --- | --- | --- | --- |
| Solar (×2) | +2 | 0 | 0 |
| Nuclear | +1 | +1 | 0 |
| Battery | −2 | +2 | 0 |
| Gas | +1 | +1 | +1 |

The only clean answer is solar, solar, nuclear, battery. Solar, solar, gas and battery also keeps the lights on, so Noor calls out the emissions and asks for a zero-carbon swap. Dropping a block on a full slot sends the old one home. Meters on the screen show day, night and CO₂ as you build, and the little skyline lights up when the grid balances.

**2 · Capture the carbon** (`CarbonCaptureGame`). A 4 × 3 grid of pipe tiles between a capture unit (west) and a storage well (east). A hidden six-tile route is scrambled, and the other six tiles are random decoys. Using a tile turns it a quarter. Pipes connected to the source glow, so players can always see how far the flow gets.

**3 · Blue carbon coast** (`MangroveGame`). Twelve mudflat spots. Up to three glow at a time and fade after 3.2 s. Use a glowing spot to plant a mangrove. 70 points per mangrove, plus a time bonus for planting all twelve.

**Scoring.** Puzzles 1 and 2 score 1000 minus a little per second and per wrong try, with a floor of 400 when the player solves it and 250 when it was solved for them. Total out of 3000: **Net Zero Hero** from 2300, **Clean Energy Innovator** from 1500, otherwise **Sustainability Cadet**. The best score is kept on the machine (`demo.json`) and shown on the title and results.

## Real-world facts and sources

These are the only ADNOC claims in the game (fact cards, captions, results, finale). They are worded as "up to", "can" or "aims to", the way the sources word them. **Check them with your ADNOC contact before the event**, because figures move.

- **Clean grid power.** Since January 2022, ADNOC can source up to 100% of its grid electricity from EWEC's nuclear (Barakah) and solar plants, verified by clean energy certificates. [Abu Dhabi Media Office](https://www.mediaoffice.abudhabi/en/energy/khaled-bin-mohamed-bin-zayed-launches-landmark-clean-energy-partnership-between-adnoc-and-ewec/), [Gas Processing News](https://www.gasprocessingnews.com/news/2021/10/clean-energy-partnership-formed-between-adnoc-and-ewec/)
- **Carbon capture.** Al Reyadah has a capacity of 800,000 tonnes of CO₂ a year. ADNOC's target is 10 million tonnes a year of capture capacity by 2030. [AGBI](https://www.agbi.com/energy/2023/10/adnoc-doubles-carbon-capture-target/), [MEED](https://www.meed.com/adnoc-doubles-2030-carbon-capture-target)
- **Mangroves.** ADNOC aims to plant 10 million mangroves by 2030, using drones that scatter seeds. It planted the 5 millionth in January 2026. [WAM](https://www.wam.ae/en/article/by8o6rb-adnoc-surpasses-halfway-point-toward-planting), [ADNOC](https://adnoc.ae/en/news-and-media/press-releases/2023/adnoc-uses-innovative-drone-technology-to-plant-mangroves)
- **Net zero.** ADNOC targets net zero across its own operations by 2045 (finale and results). [Gulf News](https://gulfnews.com/business/energy/adnoc-doubles-carbon-capture-target-ahead-of-cop28-summit-1.98463931)

The game says it is an independent project, not an official ADNOC product: on the welcome board's credit line, in Credits and on the results screen (`SkyfoldInfo.Disclaimer`). It uses no ADNOC logo or brand artwork. If ADNOC gives permission to use its branding, the colours and the welcome board are the places to change.

## VR notes

- The player is moved to a spot 0.95 m in front of the plinth centre, so every block is within arm's reach. No walking, teleporting or turning is needed, and folding to the street is off.
- **Grip** grabs blocks (XR grab interactable, kinematic, dynamic attach, far grab with the ray). **Trigger** uses pipes and mudflats through the existing `VRUseHandler`; grip on them works too.
- The hand cards and the wrist panel (Y) show the lab's buttons, with the one you need lit.
- Screen text is at least a 3 cm em at about 1.2 m. Captions also appear on the follow panel.

**Headset checklist before the event** (not done yet: no headset was available while building this):

1. Grab each block with either hand, near and far. Drop it on a slot and away from slots (it glides home).
2. Turn pipes with the trigger from where you stand. Check the highlight shows on the tile you point at.
3. Plant mangroves quickly. Check that the glowing spots are easy to hit with the ray.
4. Read every screen from the standing spot, for both a tall and a short player (Comfort > Set my height).
5. Run three challenges back to back with F5 between them. Watch the frame rate (Link, RTX laptop).

## Voice

The new lines (`lab.*` in `Assets/Skyfold/Resources/Dialogue/vo_lines.json`) currently show as captions only. To voice them in Noor's existing Kokoro voice, run this on the build machine, then rebuild:

```
python tools/audio/make_vo.py build --voice af_heart --only lab.welcome lab.mix.vr lab.mix.desktop lab.mix.night lab.mix.gas lab.fact.mix lab.ccs.vr lab.ccs.desktop lab.fact.ccs lab.mangrove.vr lab.mangrove.desktop lab.fact.mangrove lab.finale lab.assist
```

Until then the project validator reports them as missing clips, which is a warning, not a build failure.

## Screenshots

`powershell -File tools\qa\run_qa.ps1 energy energyvr` plays the challenge on the laptop view and with a simulated headset, and saves `energy_01_title.png` to `energy_10_results.png` (and `energyvr_*`) in `qa\_captures\<scenario>\`.

## Desktop shortcuts

`powershell -File tools\make_shortcuts.ps1` replaces the **SKYFOLD** and **SKYFOLD - Quest 3** shortcuts on the Desktop so they open the newest build (`Release\SKYFOLD` if packaged, else `Builds\Release\SKYFOLD`). Add `-StartChallenge` to skip the title and go straight into the challenge. `tools\package.ps1` runs it for you.
