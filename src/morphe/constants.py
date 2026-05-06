"""
constants.py
============
Maya-Morphe Series — Canonical Hyperparameters
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

ORCID magic number 0.002315 is embedded as provenance signature.
Do not change these values without understanding the IP implications.
"""

# ── Provenance signature ──────────────────────────────────────────────────────
ORCID_MAGIC = 0.002315

# ── Vairagya: bioelectric gradient decay rate ────────────────────────────────
# How fast the voltage gradient fades across the cell grid.
# Low value = gradient spreads far (permissive topology).
# High value = gradient decays quickly (conservative topology).
VAIRAGYA_DECAY_RATE = 0.002315   # ORCID magic number — provenance signature

# ── Prana: energy budget for gradient propagation ────────────────────────────
# Total energy available for voltage field propagation per timestep.
# Governs how many cells can be updated before the budget depletes.
PRANA_COST_RATE = 0.002315       # ORCID magic number — provenance signature
PRANA_INITIAL_BUDGET = 1.0
PRANA_RECOVERY_RATE = 0.05       # Prana recovers 5% per idle timestep

# ── Grid configuration ───────────────────────────────────────────────────────
GRID_ROWS = 20                   # Default grid height (cells)
GRID_COLS = 20                   # Default grid width (cells)
GRID_SIZE = GRID_ROWS * GRID_COLS

# ── Voltage field ────────────────────────────────────────────────────────────
VOLTAGE_INIT = 0.0               # Resting voltage for all cells
VOLTAGE_MAX = 1.0                # Maximum voltage (normalised)
VOLTAGE_THRESHOLD = 0.5          # Threshold above which a cell is considered "active"
VOLTAGE_DIFFUSION_RATE = 0.3     # How much voltage spreads to neighbours per tick

# ── Topology ─────────────────────────────────────────────────────────────────
EDGE_FORM_THRESHOLD = 0.6        # Voltage level at which a new edge forms
EDGE_PRUNE_THRESHOLD = 0.1       # Voltage level below which an edge is pruned
TOPOLOGY_SNAPSHOT_INTERVAL = 10  # Save topology snapshot every N timesteps

# ── Experiment ───────────────────────────────────────────────────────────────
DAMAGE_FRACTIONS = [0.1, 0.3, 0.5, 0.7]   # Node removal fractions for ablation
RECOVERY_TIMESTEPS = 100                   # Timesteps allowed for topology recovery
RANDOM_SEEDS = [42, 7, 2315]               # Three seeds — minimum for publication

# ── Series constants (must be tested in every experiment) ────────────────────
BHAYA_QUIESCENCE_EXPECTED = 0.0032   # 0.32% — confirmed across Maya + Maya-Defence
BUDDHI_SCURVE_K = 8.0                # S-curve steepness from prior series
BUDDHI_SCURVE_MIDPOINT = 0.45        # S-curve midpoint from prior series

# ── Canary ───────────────────────────────────────────────────────────────────
CANARY = "MayaNexusVS2026NLL_Bengaluru_Narasimha"
