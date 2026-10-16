using UnityEngine;

namespace Skyfold
{
    /// <summary>Swaps the courier glove between its relaxed and gripping pose from the grip trigger.</summary>
    public sealed class GloveAnimator : MonoBehaviour
    {
        public Hand hand = Hand.Left;
        public GameObject open;
        public GameObject grip;
        public float threshold = 0.55f;

        void Update()
        {
            var input = InputRouter.Instance;
            if (input == null || open == null || grip == null) return;
            float v = hand == Hand.Left ? input.GripLeft.ReadValue<float>() : input.GripRight.ReadValue<float>();
            bool closed = v > threshold;
            if (grip.activeSelf != closed) grip.SetActive(closed);
            if (open.activeSelf == closed) open.SetActive(!closed);
        }
    }
}
