using System.Collections;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace Skyfold
{
    /// <summary>
    /// "energy" and "energyvr": the Clean Energy Challenge from title to results, on the laptop and with the simulated
    /// headset. Each run plays one wrong energy mix first (gas), then solves every puzzle the way a player would, and
    /// saves a screenshot at every step, so the folder doubles as the showcase screenshot set.
    /// </summary>
    public sealed partial class QARunner
    {
        IEnumerator EnergyChallenge(bool vr)
        {
            if (vr)
            {
                SimDevices();
                m_SimPoses = true;
                StartCoroutine(SimPoseLoop());
                yield return null;
                Root.EnterSimulatedVRForQA();
            }
            else Root.ChooseDesktop();
            yield return new WaitForSecondsRealtime(1.5f);
            string p = vr ? "energyvr_" : "energy_";
            yield return Shot(p + "01_title");

            var lab = EnergyLab.Instance;
            Check(lab != null, "the Clean Energy Lab is in the scene");
            if (lab == null) yield break;
            Check(lab.LabMode, "the title shows the lab on the plinth");

            Root.StartMission(MissionCatalog.CleanEnergy);
            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "lab.mix", 5f, "energy mix is the first objective");
            Check(InputRouter.Instance.Context == InputContext.Architect, "the challenge plays in the Architect (plinth) context");
            Check(!FoldController.Instance.Allowed, "folding to the street is off during the challenge");
            Vector3 feet = PlayerRigs.Instance.FeetPosition, table = lab.transform.position;
            float reach = new Vector2(feet.x - table.x, feet.z - table.z).magnitude;
            Check(reach < 1.2f, $"the player stands at the table ({reach:0.00} m from its centre)");
            if (vr)
            {
                var token = lab.GetComponentInChildren<LabToken>(true);
                Check(token != null && token.Grab != null, "energy blocks carry an XR grab interactable");
                var button = lab.GetComponentInChildren<LabButton>(true);
                Check(button != null && button.GetComponent<XRSimpleInteractable>() != null, "pipes and mudflats carry an XR simple interactable");
                yield return SimLook(38f);
            }
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot(p + "02_mix_start");

            // A wrong try first: solar, solar, gas, battery keeps the lights on but emits.
            lab.Mix.QAPlace(EnergyMixGame.Kind.Solar, 0);
            yield return new WaitForSecondsRealtime(0.4f);
            lab.Mix.QAPlace(EnergyMixGame.Kind.Solar, 1);
            yield return new WaitForSecondsRealtime(0.4f);
            lab.Mix.QAPlace(EnergyMixGame.Kind.Gas, 2);
            yield return new WaitForSecondsRealtime(0.4f);
            lab.Mix.QAPlace(EnergyMixGame.Kind.Battery, 3);
            yield return new WaitForSecondsRealtime(0.8f);
            Check(!lab.Mix.Done && lab.Mix.Mistakes == 1, "the gas mix is called out, not accepted");
            yield return Shot(p + "03_mix_gas");
            // Swap the gas for nuclear: dropping onto a full slot sends its block home.
            lab.Mix.QAPlace(EnergyMixGame.Kind.Nuclear, 2);
            yield return WaitUntil(() => lab.Mix.Done, 2f, "solar, solar, nuclear, battery balances the grid");
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot(p + "04_mix_solved");

            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "lab.ccs", 12f, "carbon capture follows");
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot(p + "05_ccs_start");
            yield return lab.Capture.QASolve();
            yield return WaitUntil(() => lab.Capture.Done, 3f, "the pipeline reaches the storage well");
            yield return new WaitForSecondsRealtime(0.8f);
            yield return Shot(p + "06_ccs_solved");

            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "lab.mangrove", 12f, "mangroves follow");
            yield return new WaitForSecondsRealtime(3f);
            float t = 0f;
            bool shot = false;
            while (!lab.Mangroves.Done && t < 35f)
            {
                lab.Mangroves.QAPlantLit();
                if (!shot && t > 3f) { shot = true; yield return Shot(p + "07_mangrove_play"); }
                yield return new WaitForSecondsRealtime(0.7f);
                t += 0.7f;
            }
            Check(lab.Mangroves.Done && lab.Mangroves.Planted >= 6, $"mangrove round ends with plantings ({lab.Mangroves.Planted})");
            yield return new WaitForSecondsRealtime(0.8f);
            yield return Shot(p + "08_mangrove_done");

            yield return WaitUntil(() => MD.CurrentObjective != null && MD.CurrentObjective.Id == "lab.finale", 12f, "finale follows");
            yield return new WaitForSecondsRealtime(3f);
            yield return Shot(p + "09_finale");
            yield return WaitUntil(() => MD.State == MissionState.Results, 30f, "results screen");
            yield return new WaitForSecondsRealtime(1f);
            yield return Shot(p + "10_results");
            var r = MD.LastResult;
            Check(r != null && r.Score == lab.TotalScore && r.Score > 0, $"the result carries the lab score ({r?.Score})");
            Log($"clean energy run: score {r?.Score} ({EnergyLab.Rank(r != null ? r.Score : 0).title}), {MD.PlayTime:0} s played");
            Check(MD.PlayTime < 200f, $"a quick player finishes in about three minutes ({MD.PlayTime:0} s)");

            if (vr)
            {
                m_SimPoses = false;
                yield return null;
                SimRemoveDevices();
            }
        }
    }
}
