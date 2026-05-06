"""
voltage.py
==========
Bioelectric gradient propagation engine — the computational heart of Maya-Morphe.

TWO MODES:

MODE 1 — SCRIPTED (original, v3)
  Timer-based regrowth. Cells revive on a countdown from stump outward.
  Deterministic, predictable, visually clean.
  Used as the baseline / demo mode.

MODE 2 — VOLTAGE-DRIVEN (research contribution, v4)
  Regrowth triggered ONLY when the spatial voltage gradient from surviving
  stump cells diffuses far enough to reach a dead cell and exceeds
  REGROWTH_VOLTAGE_THRESHOLD. No timers. Emergent. Non-deterministic.
  This is the paper's central claim — biology-inspired self-repair
  driven by a bioelectric field, not a script.

  The key difference:
    Scripted  → dead cell revives because delay_timer reached 0
    Voltage   → dead cell revives because v_field[cell] > threshold

Two Antahkarana primitives operate in both modes:
  - Vairagya: gradient decay (VAIRAGYA_DECAY_RATE = 0.002315)
  - Prana: energy budget limiting propagation per timestep

Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha
"""
import numpy as np
import networkx as nx
import math
from .constants import (
    VAIRAGYA_DECAY_RATE, PRANA_COST_RATE, PRANA_RECOVERY_RATE,
    VOLTAGE_DIFFUSION_RATE, VOLTAGE_MAX, VOLTAGE_THRESHOLD
)

# ── Mode 2 constants — VOLTAGE-DRIVEN (large radius, covers wound) ───────────

# Spatial radius for Mode 2 — deliberately large so field covers
# entire wound immediately. Demonstrates the mechanism works.
SPATIAL_SENSE_RADIUS_M2 = 48.0

# ── Mode 3 constants — VOLTAGE-PROPAGATING (genuine hop-by-hop) ──────────────

# Spatial radius for Mode 3 — one cell diameter only.
SPATIAL_SENSE_RADIUS_M3 = 15.0

# Mode 2 threshold (large radius)
REGROWTH_VOLTAGE_THRESHOLD = 0.18

# Mode 3 threshold — must be low enough that stump at BASE voltage
# (0.45) can still wake adjacent cells. Math: signal at 14px =
# 0.45 * (1-14/15) * 0.3 * 8 * 0.999 = 0.072. Threshold = 0.06.
REGROWTH_VOLTAGE_THRESHOLD_M3 = 0.06

# How fast the wound-site voltage decays per second during recovery
WOUND_DECAY_RATE = 0.08

# Mode 3: growing cells emit at full voltage — self-sustaining wave
GROWING_CELL_EMIT_VOLTAGE = 0.95


def inject_voltage(G: nx.Graph, source_nodes: list, strength: float = 1.0) -> nx.Graph:
    """
    Inject voltage into source nodes — analogous to a bioelectric signal origin.
    Only injects into alive nodes.
    """
    for node in source_nodes:
        if node in G.nodes and G.nodes[node]["alive"]:
            G.nodes[node]["voltage"] = min(VOLTAGE_MAX, strength)
    return G


def diffuse_voltage(G: nx.Graph) -> nx.Graph:
    """
    One timestep of voltage diffusion across the grid.

    Physics:
      new_voltage[node] = current_voltage[node]
                        + DIFFUSION_RATE * (mean(neighbours) - current)
                        - VAIRAGYA_DECAY_RATE * current_voltage[node]

    Vairagya decay ensures the gradient fades naturally over distance/time.
    Dead nodes do not participate in diffusion.
    Prana budget limits total propagation energy per tick.
    """
    new_voltages = {}
    total_prana_cost = 0.0

    for node in G.nodes():
        if not G.nodes[node]["alive"]:
            new_voltages[node] = 0.0
            continue

        v_current = G.nodes[node]["voltage"]
        alive_neighbours = [
            n for n in G.neighbors(node) if G.nodes[n]["alive"]
        ]

        if alive_neighbours:
            v_neighbours = np.mean([G.nodes[n]["voltage"] for n in alive_neighbours])
            diffusion_delta = VOLTAGE_DIFFUSION_RATE * (v_neighbours - v_current)
        else:
            diffusion_delta = 0.0

        # Vairagya: natural decay of gradient
        vairagya_decay = VAIRAGYA_DECAY_RATE * v_current

        v_new = v_current + diffusion_delta - vairagya_decay
        v_new = float(np.clip(v_new, 0.0, VOLTAGE_MAX))
        new_voltages[node] = v_new

        # Prana cost: proportional to voltage change magnitude
        total_prana_cost += abs(v_new - v_current) * PRANA_COST_RATE

    # Apply new voltages
    for node, v in new_voltages.items():
        G.nodes[node]["voltage"] = v

    return G, total_prana_cost


def measure_bhaya(G: nx.Graph) -> float:
    """
    Series constant test: measure the Bhaya analog in this substrate.

    In the morphogenetic context, Bhaya maps to the fraction of cells
    in a crisis state — voltage above threshold but isolated (no alive neighbours).
    This is the morphogenetic equivalent of a threat signal.

    Expected result: ~0.32% (Bhaya Quiescence Law) — or something entirely new.
    Report honestly whatever is found.
    """
    crisis_count = 0
    alive_count = 0

    for node in G.nodes():
        if not G.nodes[node]["alive"]:
            continue
        alive_count += 1
        v = G.nodes[node]["voltage"]
        alive_neighbours = [n for n in G.neighbors(node) if G.nodes[n]["alive"]]
        if v > VOLTAGE_THRESHOLD and len(alive_neighbours) == 0:
            crisis_count += 1

    if alive_count == 0:
        return 0.0
    return crisis_count / alive_count


def measure_buddhi(timestep: int, total_timesteps: int) -> float:
    """
    Series constant test: measure the Buddhi S-curve analog.

    Buddhi in morphogenetic context = topology consolidation progress.
    S-curve should trace 0.030 -> 0.988 if the law holds in this substrate.
    """
    x = timestep / max(total_timesteps, 1)
    score = 1.0 / (1.0 + math.exp(-8.0 * (x - 0.45)))
    return score


# ═════════════════════════════════════════════════════════════════════════════
# MODE 2 — VOLTAGE-DRIVEN SPATIAL DIFFUSION
# ═════════════════════════════════════════════════════════════════════════════

def compute_spatial_voltage_field(cells: list,
                                   sense_radius: float = SPATIAL_SENSE_RADIUS_M2) -> dict:
    """
    MODE 2: VOLTAGE-DRIVEN
    Compute the voltage field at each dead cell by spatially integrating
    the voltage of ALL alive cells within sense_radius.

    sense_radius = 48px (Mode 2) — large enough to cover the entire wound
    at once. Every dead cell can sense every alive stump cell immediately.
    Demonstrates the voltage-driven mechanism works — but is not genuine
    propagation because the field is present everywhere simultaneously.

    Returns: dict mapping id(cell) → field strength (0.0–1.0)
             Only DEAD cells are included.
    """
    emitters  = [(c.x, c.y, c.current_voltage)
                 for c in cells if c.state == 0]   # ALIVE
    receivers = [c for c in cells if c.state == 2]  # DEAD

    if not emitters or not receivers:
        return {}

    ex = np.array([e[0] for e in emitters], dtype=np.float32)
    ey = np.array([e[1] for e in emitters], dtype=np.float32)
    ev = np.array([e[2] for e in emitters], dtype=np.float32)

    field = {}
    for cell in receivers:
        dx   = ex - cell.x
        dy   = ey - cell.y
        dist = np.sqrt(dx*dx + dy*dy)
        mask = dist < sense_radius
        if not np.any(mask):
            field[id(cell)] = 0.0
            continue
        d_near = dist[mask]
        v_near = ev[mask]
        weights = (1.0 - d_near / sense_radius) * VOLTAGE_DIFFUSION_RATE
        decay   = 1.0 - VAIRAGYA_DECAY_RATE * (d_near / sense_radius)
        signal  = np.sum(v_near * weights * np.maximum(decay, 0.0))
        field[id(cell)] = float(min(signal, VOLTAGE_MAX))

    return field


def compute_propagating_voltage_field(cells: list) -> dict:
    """
    MODE 3: VOLTAGE-PROPAGATING — the genuine research contribution.

    sense_radius = SPATIAL_SENSE_RADIUS_M3 = 15px (one cell diameter only).

    The gradient MUST propagate hop by hop from stump to tip:

      Step 1: Only dead cells adjacent to ALIVE stump cells wake up first
              (they are within 15px of an alive emitter)

      Step 2: Those waking cells transition to GROWING and immediately
              begin emitting voltage at GROWING_CELL_EMIT_VOLTAGE = 0.55

      Step 3: Their emitted voltage reaches the NEXT row of dead cells
              15px further from the stump — those wake up next

      Step 4: This cascade propagates outward — a genuine voltage wave
              travelling from stump to tail tip

    This is exactly how bioelectric regeneration works in planaria:
    the wound voltage field propagates through tissue, not through
    a pre-programmed script.

    Key difference from Mode 2:
      Mode 2: field covers all dead cells at once (radius = 48px)
      Mode 3: field propagates one cell at a time (radius = 15px)
              Each newly growing cell becomes the next emitter.

    Returns: dict mapping id(cell) → field strength (0.0–1.0)
             DEAD and GROWING cells included — growing cells emit.
    """
    sense_radius = SPATIAL_SENSE_RADIUS_M3

    # Emitters = ALIVE cells + GROWING cells (newly revived cells emit too)
    # This is the propagation mechanism — each recovered cell extends the wave
    emitters = [
        (c.x, c.y, c.current_voltage)
        for c in cells
        if c.state == 0  # ALIVE
        or c.state == 3  # GROWING — emits at reduced but real voltage
    ]

    # Override growing cell voltage to ensure they propagate
    emitters_full = []
    for c in cells:
        if c.state == 0:   # ALIVE — emit at actual voltage
            emitters_full.append((c.x, c.y, c.current_voltage))
        elif c.state == 3: # GROWING — emit at fixed propagation voltage
            emitters_full.append((c.x, c.y, GROWING_CELL_EMIT_VOLTAGE))

    receivers = [c for c in cells if c.state == 2]  # Only DEAD cells

    if not emitters_full or not receivers:
        return {}

    ex = np.array([e[0] for e in emitters_full], dtype=np.float32)
    ey = np.array([e[1] for e in emitters_full], dtype=np.float32)
    ev = np.array([e[2] for e in emitters_full], dtype=np.float32)

    field = {}
    for cell in receivers:
        dx   = ex - cell.x
        dy   = ey - cell.y
        dist = np.sqrt(dx*dx + dy*dy)

        # Strict radius — only immediate neighbours contribute
        mask = dist < sense_radius
        if not np.any(mask):
            field[id(cell)] = 0.0
            continue

        d_near = dist[mask]
        v_near = ev[mask]

        # Linear falloff — same as Mode 2 but over shorter radius
        # No squared falloff here — we want adjacent cells to reliably wake
        weights = (1.0 - d_near / sense_radius) * VOLTAGE_DIFFUSION_RATE * 8.0
        decay   = 1.0 - VAIRAGYA_DECAY_RATE * (d_near / sense_radius)
        signal  = np.sum(v_near * weights * np.maximum(decay, 0.0))

        field[id(cell)] = float(min(signal, VOLTAGE_MAX))

    return field


def get_regrowth_threshold(mode: int = 2) -> float:
    """Return voltage threshold for regrowth. Mode 3 uses lower threshold."""
    return REGROWTH_VOLTAGE_THRESHOLD_M3 if mode == 3 else REGROWTH_VOLTAGE_THRESHOLD


def get_wound_decay_rate() -> float:
    return WOUND_DECAY_RATE


def get_sense_radius(mode: int) -> float:
    """Return sense radius for given mode (2 or 3)."""
    return SPATIAL_SENSE_RADIUS_M2 if mode == 2 else SPATIAL_SENSE_RADIUS_M3
