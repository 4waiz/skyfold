using System;
using UnityEngine;

namespace Skyfold
{
    /// <summary>Where the power cell can sit: the depot dock, the car's cradle or the substation.</summary>
    public sealed class CellSocket : WorldInteractable
    {
        public CellLocation location = CellLocation.Dock;
        public Transform attach;
        public bool allowRemove = true;
        public bool lockWhenFilled;
        public Renderer glow;

        public PowerCell Occupant { get; private set; }
        public bool Accepts => Occupant == null && isActiveAndEnabled;
        public event Action<CellSocket> Inserted;
        public event Action<CellSocket> Removed;

        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock m_Block;

        protected override void Awake()
        {
            base.Awake();
            if (attach == null) attach = transform;
            m_Block = new MaterialPropertyBlock();
        }

        public override bool CanInteract(InteractorKind who)
        {
            if (!base.CanInteract(who) || who != InteractorKind.Desktop) return false;
            var cell = PowerCell.Instance;
            if (cell == null) return false;
            if (Occupant == null) return cell.HeldOnDesktop;
            return allowRemove;
        }

        public override string Prompt
        {
            get
            {
                if (Occupant != null) return "Take the hydrogen cell";
                switch (location)
                {
                    case CellLocation.CarCradle: return "Load the cell into the cradle";
                    case CellLocation.Substation: return "Insert the cell";
                    default: return "Put the cell back";
                }
            }
        }

        public override string BlockedReason
        {
            get
            {
                if (Occupant != null && !allowRemove) return "The cell is powering the microgrid.";
                if (Occupant == null && PowerCell.Instance != null && !PowerCell.Instance.HeldOnDesktop) return "Pick up the hydrogen cell first.";
                return null;
            }
        }

        public override void Interact(InteractorKind who)
        {
            var cell = PowerCell.Instance;
            if (cell == null) return;
            if (Occupant == null && cell.HeldOnDesktop) cell.InsertInto(this);
            else if (Occupant != null && allowRemove) cell.Interact(who);
        }

        public void OnInserted(PowerCell cell, bool silent = false)
        {
            Occupant = cell;
            if (lockWhenFilled) allowRemove = false;
            if (!silent) Inserted?.Invoke(this);
        }

        public void OnRemoved(PowerCell cell)
        {
            if (Occupant == cell) Occupant = null;
            Removed?.Invoke(this);
        }

        public void ResetSocket(bool removable)
        {
            allowRemove = removable;
            Occupant = null;
        }

        void Update()
        {
            if (glow == null) return;
            bool want = Occupant == null && PowerCell.Instance != null && PowerCell.Instance.Location == CellLocation.Held;
            glow.GetPropertyBlock(m_Block);
            float k = want ? 2.2f + Mathf.Sin(Time.time * 5f) : (Occupant != null ? 1.2f : 0.25f);
            m_Block.SetColor(EmissionId, new Color(0.21f, 0.88f, 0.82f) * k);
            glow.SetPropertyBlock(m_Block);
        }
    }
}
