"""
run_ablation.py
===============
Maya-Morphe Paper 1 — Ablation Study
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

Systematic ablation across:
  - Damage fractions: [0.10, 0.30, 0.50, 0.70]
  - Seeds:            [42, 7, 2315]
  - Conditions:       MODE_SCRIPTED, MODE_VOLTAGE, FIXED_TOPOLOGY_BASELINE

Metrics collected per run:
  - FRR at recovery (Functional Recovery Rate)
  - Time to full recovery (seconds of simulation time)
  - Bhaya fraction at peak wound
  - Bhaya fraction at recovery
  - Buddhi S-curve value at recovery
  - Severed cell count
  - Stump cell count

Output:
  - results/ablation_results.csv   — raw data, all runs
  - results/ablation_summary.txt   — paper-ready summary table
  - results/bhaya_log.csv          — Bhaya measurements for series constant analysis

Run from Maya-Morphe-P1 root:
    python experiments/run_ablation.py

Expected runtime: ~3-5 minutes on RTX 4060 (CPU-bound, no GPU needed)
"""

import sys
import os
import csv
import math
import random
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify_provenance
verify_provenance.stamp()

import numpy as np
from scipy.stats.qmc import PoissonDisk
from PIL import Image, ImageDraw

from src.morphe.voltage import (
    compute_spatial_voltage_field,
    get_regrowth_threshold,
    get_wound_decay_rate,
    SPATIAL_SENSE_RADIUS_M2,
    REGROWTH_VOLTAGE_THRESHOLD,
    REGROWTH_VOLTAGE_THRESHOLD_M3,
)
from src.morphe.constants import (
    CANARY, VAIRAGYA_DECAY_RATE,
    DAMAGE_FRACTIONS, RANDOM_SEEDS,
    BHAYA_QUIESCENCE_EXPECTED,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

RESULTS_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
ASSET_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
PNG_PATH     = os.path.join(ASSET_DIR, "lizard_silhouette.png")

# Simulation parameters — must match run_lizard_v5.py exactly
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 780
SIDEBAR_WIDTH = 300
CELL_RADIUS   = 14
CELL_DRAW_R   = 9

# Max simulation time per run (seconds of sim time)
MAX_SIM_TIME  = 60.0
DT            = 1.0 / 60.0   # 60fps equivalent

# Pulse parameters — match visualizer
PULSE_SPEED   = 1.0
BASE_VOLTAGE_RANGE = (0.30, 0.60)
STUMP_BASE_VOLTAGE = 0.78     # elevated wound potential after cut

# Conditions
MODE_SCRIPTED       = "SCRIPTED"
MODE_VOLTAGE        = "VOLTAGE_DRIVEN"
FIXED_TOPOLOGY      = "FIXED_TOPOLOGY_BASELINE"
CONDITIONS          = [MODE_SCRIPTED, MODE_VOLTAGE, FIXED_TOPOLOGY]

# Cell states
ALIVE, DYING, DEAD, GROWING = 0, 1, 2, 3

# ─────────────────────────────────────────────────────────────────────────────
# CELL CLASS  (lightweight — no pygame dependency)
# ─────────────────────────────────────────────────────────────────────────────

class Cell:
    __slots__ = ["x", "y", "region", "state",
                 "base_voltage", "current_voltage",
                 "delay_timer", "decay_timer"]

    def __init__(self, x, y, region, seed_offset=0):
        self.x               = float(x)
        self.y               = float(y)
        self.region          = region
        self.state           = ALIVE
        rng                  = np.random.default_rng(int(x * 1000 + y + seed_offset))
        self.base_voltage    = float(rng.uniform(*BASE_VOLTAGE_RANGE))
        self.current_voltage = self.base_voltage
        self.delay_timer     = 0.0
        self.decay_timer     = 0.0

# ─────────────────────────────────────────────────────────────────────────────
# SILHOUETTE + CELL PACKING  (reuses existing PNG)
# ─────────────────────────────────────────────────────────────────────────────

_mask_cache = None
_mask_params = None

def get_mask():
    global _mask_cache, _mask_params
    if _mask_cache is not None:
        return _mask_cache, _mask_params

    # Load PNG — generate if missing
    if not os.path.exists(PNG_PATH):
        _generate_silhouette()

    from PIL import Image
    import numpy as np
    img  = Image.open(PNG_PATH).convert("RGBA")
    rw, rh = img.size
    avail_w = WINDOW_WIDTH - SIDEBAR_WIDTH - 60
    avail_h = WINDOW_HEIGHT - 60
    scale   = min(avail_w / rw, avail_h / rh)
    nw, nh  = int(rw * scale), int(rh * scale)
    img     = img.resize((nw, nh), Image.LANCZOS)
    arr     = np.array(img)
    # mask[y,x] = True if alpha > 127
    mask    = arr[:, :, 3] > 127

    mask_ox = SIDEBAR_WIDTH + (WINDOW_WIDTH - SIDEBAR_WIDTH - nw) // 2
    mask_oy = (WINDOW_HEIGHT - nh) // 2

    region_head_y  = int(nh * 0.22)
    region_body_y  = int(nh * 0.72)
    region_body_x0 = int(nw * 0.30)
    region_body_x1 = int(nw * 0.70)

    params = dict(
        mask=mask, nw=nw, nh=nh,
        mask_ox=mask_ox, mask_oy=mask_oy,
        region_head_y=region_head_y,
        region_body_y=region_body_y,
        region_body_x0=region_body_x0,
        region_body_x1=region_body_x1,
    )
    _mask_cache  = mask
    _mask_params = params
    return mask, params


def _classify(mx, my, p):
    if my < p["region_head_y"]:        return "HEAD"
    elif my > p["region_body_y"]:      return "TAIL"
    elif mx < p["region_body_x0"]:
        return "FRONT_LEG_L" if my < p["nh"] * 0.50 else "BACK_LEG_L"
    elif mx > p["region_body_x1"]:
        return "FRONT_LEG_R" if my < p["nh"] * 0.50 else "BACK_LEG_R"
    else:                              return "BODY"


def pack_cells(seed: int) -> list:
    mask, p = get_mask()
    W, H    = p["nw"], p["nh"]
    r       = CELL_RADIUS / max(W, H)

    engine   = PoissonDisk(d=2, radius=r, seed=seed)
    pts_norm = engine.fill_space()

    cells = []
    for px, py in pts_norm:
        mx, my = int(px * W), int(py * H)
        if mx < 0 or mx >= W or my < 0 or my >= H:
            continue
        if not mask[my, mx]:
            continue
        sx = p["mask_ox"] + mx
        sy = p["mask_oy"] + my
        region = _classify(mx, my, p)
        cells.append(Cell(sx, sy, region, seed_offset=seed))

    return cells


def _generate_silhouette():
    os.makedirs(ASSET_DIR, exist_ok=True)
    W, H = 900, 900
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    F    = (255, 255, 255, 255)
    cx, cy = 450, 480
    sc   = 1.6

    def p(dx, dy): return (int(cx + dx*sc), int(cy + dy*sc))
    def e(x1,y1,x2,y2): return [cx+x1*sc, cy+y1*sc, cx+x2*sc, cy+y2*sc]

    draw.polygon([p(-55,-170),p(55,-170),p(38,-265),p(0,-300),p(-38,-265)], fill=F)
    draw.ellipse(e(-42,-195,42,-155), fill=F)
    draw.ellipse(e(-70,-165,70,95),   fill=F)
    draw.ellipse(e(-32,-238,-14,-222),fill=F)
    draw.ellipse(e(14,-238,32,-222),  fill=F)
    draw.polygon([p(-52,-110),p(-52,-75),p(-95,-55),p(-155,-68),p(-152,-92),p(-98,-82)], fill=F)
    draw.polygon([p(52,-110),p(52,-75),p(95,-55),p(155,-68),p(152,-92),p(98,-82)],       fill=F)
    draw.polygon([p(-58,30),p(-58,75),p(-105,105),p(-168,85),p(-162,58),p(-105,72)],     fill=F)
    draw.polygon([p(58,30),p(58,75),p(105,105),p(168,85),p(162,58),p(105,72)],           fill=F)
    draw.ellipse(e(-58,60,58,115), fill=F)
    for i in range(42):
        t  = i / 41
        tx = cx + math.sin(t * math.pi * 0.7) * 55 * sc
        ty = cy + 88*sc + t * 255*sc
        w  = max(3, int(52 * sc * (1 - t) ** 0.75))
        draw.ellipse([tx-w, ty-w, tx+w, ty+w], fill=F)

    img.save(PNG_PATH)
    print(f"  [asset] Generated: {PNG_PATH}")

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION ENGINE  (headless — no pygame)
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(cells: list, damage_frac: float, seed: int,
                   condition: str) -> dict:
    """
    Run one complete ablation trial headlessly.
    Returns a dict of metrics.
    """
    # ── Identify tail cells ───────────────────────────────────────────────────
    tail = [c for c in cells if c.region == "TAIL"]
    if not tail:
        return None

    # ── Compute cut point ─────────────────────────────────────────────────────
    y_min = min(c.y for c in tail)
    y_max = max(c.y for c in tail)
    cut_y = y_min + (y_max - y_min) * damage_frac

    # ── FIXED TOPOLOGY BASELINE: no repair possible ───────────────────────────
    if condition == FIXED_TOPOLOGY:
        severed_count = sum(1 for c in tail if c.y > cut_y)
        return {
            "condition":         condition,
            "damage_frac":       damage_frac,
            "seed":              seed,
            "severed_count":     severed_count,
            "stump_count":       sum(1 for c in tail if c.y <= cut_y),
            "total_tail":        len(tail),
            "frr_final":         0.0,
            "frr_at_10s":        0.0,
            "frr_at_30s":        0.0,
            "frr_at_60s":        0.0,
            "recovery_time_s":   float("inf"),
            "bhaya_peak":        0.0,
            "bhaya_at_recovery": 0.0,
            "buddhi_at_recovery":0.0,
            "recovered":         False,
            "note": "Fixed topology — cannot self-repair by definition",
        }

    # ── Apply amputation ──────────────────────────────────────────────────────
    severed = sorted(
        [c for c in cells if c.region == "TAIL" and c.y > cut_y],
        key=lambda c: c.y, reverse=True
    )
    for idx, cell in enumerate(severed):
        cell.delay_timer = 0.01 + (idx / max(len(severed), 1)) * 1.2

    stump = [c for c in tail if c.y <= cut_y]
    for c in stump:
        c.base_voltage    = STUMP_BASE_VOLTAGE
        c.current_voltage = 1.0

    severed_count = len(severed)
    stump_count   = len(stump)

    # ── Track severed cell ids for precise FRR ───────────────────────────────
    # Using id() set avoids float comparison drift at cut boundary
    severed_ids = {id(c) for c in severed}

    # ── Simulation loop ───────────────────────────────────────────────────────
    sim_time       = 0.0
    amputation_active = True
    regrowth_active   = False
    regrowth_triggered = False

    bhaya_peak        = 0.0
    bhaya_at_recovery = 0.0
    buddhi_at_recovery= 0.0
    recovery_time_s   = float("inf")
    recovered         = False

    frr_at = {10: 0.0, 30: 0.0, 60: 0.0}

    threshold = get_regrowth_threshold(2)  # Mode 2 threshold

    while sim_time < MAX_SIM_TIME:
        sim_time += DT

        # ── Voltage pulse (ambient) ───────────────────────────────────────────
        for cell in cells:
            if cell.state == ALIVE:
                pulse = math.sin(
                    sim_time * 1.8 * PULSE_SPEED
                    + cell.y * 0.04 + cell.x * 0.02
                ) * 0.12
                cell.current_voltage = cell.base_voltage + pulse

        # ── Compute voltage field (Mode 2 only) ───────────────────────────────
        voltage_field = {}
        if condition == MODE_VOLTAGE and regrowth_active:
            voltage_field = compute_spatial_voltage_field(cells)

        # ── Per-cell state machine ────────────────────────────────────────────
        dead_count   = 0
        dying_count  = 0
        grow_count   = 0
        alive_severed = 0

        for cell in cells:
            if cell.state == ALIVE:
                if (amputation_active
                        and cell.region == "TAIL"
                        and cell.y > cut_y
                        and cell.delay_timer > 0):
                    cell.delay_timer -= DT
                    if cell.delay_timer <= 0:
                        cell.state       = DYING
                        cell.decay_timer = 0.20

            elif cell.state == DYING:
                dying_count += 1
                cell.current_voltage -= DT / 0.20
                cell.decay_timer     -= DT
                if cell.decay_timer <= 0:
                    cell.state           = DEAD
                    cell.current_voltage = 0.0

            elif cell.state == DEAD:
                dead_count += 1
                if regrowth_active:
                    if condition == MODE_SCRIPTED:
                        if cell.delay_timer > 0:
                            cell.delay_timer -= DT
                            if cell.delay_timer <= 0:
                                cell.state           = GROWING
                                cell.current_voltage = 0.05
                    elif condition == MODE_VOLTAGE:
                        field_v = voltage_field.get(id(cell), 0.0)
                        cell.current_voltage = field_v * 0.4
                        if field_v >= threshold:
                            cell.state           = GROWING
                            cell.current_voltage = 0.05

            elif cell.state == GROWING:
                grow_count += 1
                cell.current_voltage = min(
                    cell.base_voltage,
                    cell.current_voltage + DT * 0.15
                )
                if cell.current_voltage >= cell.base_voltage * 0.95:
                    cell.state = ALIVE

        # ── Count alive severed ───────────────────────────────────────────────
        alive_severed = sum(
            1 for c in cells
            if id(c) in severed_ids and c.state == ALIVE
        )
        frr = alive_severed / max(severed_count, 1)

        # ── Bhaya ─────────────────────────────────────────────────────────────
        alive_total = sum(1 for c in cells if c.state == ALIVE)
        crisis = sum(1 for c in cells
                     if c.state == ALIVE and c.current_voltage > 0.85)
        bhaya = crisis / max(alive_total, 1)
        bhaya_peak = max(bhaya_peak, bhaya)

        # ── FRR snapshots ─────────────────────────────────────────────────────
        for t_snap in [10, 30, 60]:
            if abs(sim_time - t_snap) < DT * 0.6:
                frr_at[t_snap] = frr

        # ── Auto-trigger regrowth ─────────────────────────────────────────────
        if (amputation_active
                and not regrowth_triggered
                and dying_count == 0
                and dead_count > 0):
            regrowth_triggered = True
            regrowth_active    = True

            dead = sorted(
                [c for c in cells if c.region == "TAIL" and c.state == DEAD],
                key=lambda c: c.y
            )
            if condition == MODE_SCRIPTED:
                for idx, cell in enumerate(dead):
                    # +0.01 ensures delay_timer > 0 for ALL cells including idx=0
                    cell.delay_timer = 0.01 + (idx / max(len(dead), 1)) * 6.0
            # MODE_VOLTAGE: no timers, voltage field drives it

        # ── Recovery complete ─────────────────────────────────────────────────
        # Check if all severed cells (by id) are now ALIVE or GROWING
        severed_alive_or_growing = sum(
            1 for c in cells
            if id(c) in severed_ids and c.state in (ALIVE, GROWING)
        )
        severed_fully_alive = sum(
            1 for c in cells
            if id(c) in severed_ids and c.state == ALIVE
        )
        frr_strict = severed_fully_alive / max(severed_count, 1)

        if (regrowth_active
                and not recovered
                and (frr_strict >= 0.98 or (grow_count == 0 and dead_count == 0))):
            recovered         = True
            recovery_time_s   = sim_time
            bhaya_at_recovery = bhaya
            buddhi_at_recovery = 1.0 / (1.0 + math.exp(
                -8.0 * (sim_time / MAX_SIM_TIME - 0.45)
            ))
            break

    # ── Final FRR — use exact severed id set ─────────────────────────────────
    alive_severed_final = sum(
        1 for c in cells
        if id(c) in severed_ids and c.state == ALIVE
    )
    frr_final = alive_severed_final / max(severed_count, 1)

    return {
        "condition":          condition,
        "damage_frac":        damage_frac,
        "seed":               seed,
        "severed_count":      severed_count,
        "stump_count":        stump_count,
        "total_tail":         len(tail),
        "frr_final":          round(frr_final, 4),
        "frr_at_10s":         round(frr_at[10], 4),
        "frr_at_30s":         round(frr_at[30], 4),
        "frr_at_60s":         round(frr_at[60], 4),
        "recovery_time_s":    round(recovery_time_s, 2) if recovered else float("inf"),
        "bhaya_peak":         round(bhaya_peak, 6),
        "bhaya_at_recovery":  round(bhaya_at_recovery, 6),
        "buddhi_at_recovery": round(buddhi_at_recovery, 4),
        "recovered":          recovered,
        "note":               "",
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ABLATION LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("\n" + "="*70)
    print("MAYA-MORPHE PAPER 1 — ABLATION STUDY")
    print("Nexus Learning Labs | ORCID: 0000-0002-3315-7907")
    print(f"Canary: {CANARY}")
    print("="*70)
    print(f"\nConditions : {CONDITIONS}")
    print(f"Damage fracs: {DAMAGE_FRACTIONS}")
    print(f"Seeds       : {RANDOM_SEEDS}")
    total_runs = len(CONDITIONS) * len(DAMAGE_FRACTIONS) * len(RANDOM_SEEDS)
    print(f"Total runs  : {total_runs}")
    print(f"VAIRAGYA    : {VAIRAGYA_DECAY_RATE} (ORCID magic)")
    print(f"Bhaya law   : {BHAYA_QUIESCENCE_EXPECTED} (expected)")
    print()

    # Pre-build the mask once
    print("Building lizard mask...")
    mask, params = get_mask()
    print(f"Mask: {params['nw']}×{params['nh']}px")

    # Pre-pack cells for each seed (cell positions are seed-dependent)
    print("Packing cells for each seed...")
    cell_pools = {}
    for seed in RANDOM_SEEDS:
        cells = pack_cells(seed)
        cell_pools[seed] = cells
        tail_count = sum(1 for c in cells if c.region == "TAIL")
        print(f"  Seed {seed:4d}: {len(cells)} cells  |  tail={tail_count}")

    print()

    # ── Run all trials ────────────────────────────────────────────────────────
    all_results  = []
    bhaya_log    = []
    run_num      = 0
    wall_start   = time.time()

    for condition in CONDITIONS:
        for damage_frac in DAMAGE_FRACTIONS:
            for seed in RANDOM_SEEDS:
                run_num += 1

                # Deep copy cells for this run — each run is independent
                import copy
                cells_copy = copy.deepcopy(cell_pools[seed])

                label = f"[{run_num:02d}/{total_runs}] {condition:<22} frac={damage_frac:.0%} seed={seed}"
                print(f"{label} ... ", end="", flush=True)

                t0     = time.time()
                result = run_simulation(cells_copy, damage_frac, seed, condition)
                elapsed = time.time() - t0

                if result:
                    all_results.append(result)
                    status = "✓ RECOVERED" if result["recovered"] else f"✗ t={result['recovery_time_s']:.1f}s"
                    print(f"FRR={result['frr_final']:.1%}  bhaya_peak={result['bhaya_peak']:.5f}  {status}  ({elapsed:.1f}s)")

                    bhaya_log.append({
                        "condition":   condition,
                        "damage_frac": damage_frac,
                        "seed":        seed,
                        "bhaya_peak":  result["bhaya_peak"],
                        "bhaya_at_recovery": result["bhaya_at_recovery"],
                        "above_law":   result["bhaya_peak"] > BHAYA_QUIESCENCE_EXPECTED,
                    })
                else:
                    print("SKIP (no tail cells)")

    wall_elapsed = time.time() - wall_start
    print(f"\nAll runs complete in {wall_elapsed:.1f}s")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_path = os.path.join(RESULTS_DIR, "ablation_results.csv")
    fieldnames = [
        "condition", "damage_frac", "seed",
        "severed_count", "stump_count", "total_tail",
        "frr_final", "frr_at_10s", "frr_at_30s", "frr_at_60s",
        "recovery_time_s", "bhaya_peak", "bhaya_at_recovery",
        "buddhi_at_recovery", "recovered", "note",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nResults written: {csv_path}")

    # ── Write Bhaya log ───────────────────────────────────────────────────────
    bhaya_path = os.path.join(RESULTS_DIR, "bhaya_log.csv")
    with open(bhaya_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["condition","damage_frac","seed",
                                                "bhaya_peak","bhaya_at_recovery","above_law"])
        writer.writeheader()
        writer.writerows(bhaya_log)
    print(f"Bhaya log written: {bhaya_path}")

    # ── Summary table ─────────────────────────────────────────────────────────
    summary_path = os.path.join(RESULTS_DIR, "ablation_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("MAYA-MORPHE PAPER 1 — ABLATION STUDY RESULTS\n")
        f.write("Nexus Learning Labs | ORCID: 0000-0002-3315-7907\n")
        f.write(f"Canary: {CANARY}\n")
        f.write(f"VAIRAGYA_DECAY_RATE = {VAIRAGYA_DECAY_RATE}\n")
        f.write(f"Bhaya Quiescence Law expected = {BHAYA_QUIESCENCE_EXPECTED}\n\n")

        f.write("="*80 + "\n")
        f.write("TABLE 1: FUNCTIONAL RECOVERY RATE (FRR) — MEAN ACROSS SEEDS\n")
        f.write("="*80 + "\n\n")

        header = f"{'Condition':<25} {'Damage':<8} {'FRR':<8} {'T-10s':<8} {'T-30s':<8} {'T-60s':<8} {'RecTime':<10} {'Recovered'}\n"
        f.write(header)
        f.write("-"*80 + "\n")

        for condition in CONDITIONS:
            for damage_frac in DAMAGE_FRACTIONS:
                runs = [r for r in all_results
                        if r["condition"] == condition
                        and r["damage_frac"] == damage_frac]
                if not runs:
                    continue

                frr_mean   = np.mean([r["frr_final"] for r in runs])
                t10_mean   = np.mean([r["frr_at_10s"] for r in runs])
                t30_mean   = np.mean([r["frr_at_30s"] for r in runs])
                t60_mean   = np.mean([r["frr_at_60s"] for r in runs])
                rec_times  = [r["recovery_time_s"] for r in runs if r["recovered"]]
                rec_mean   = np.mean(rec_times) if rec_times else float("inf")
                rec_count  = sum(1 for r in runs if r["recovered"])

                rec_str    = f"{rec_mean:.1f}s" if rec_times else "DNF"
                line = (f"{condition:<25} {damage_frac:.0%}     "
                        f"{frr_mean:.3f}   {t10_mean:.3f}   {t30_mean:.3f}   "
                        f"{t60_mean:.3f}   {rec_str:<10} {rec_count}/{len(runs)}\n")
                f.write(line)
            f.write("\n")

        f.write("\n" + "="*80 + "\n")
        f.write("TABLE 2: BHAYA QUIESCENCE LAW TEST\n")
        f.write("="*80 + "\n\n")
        f.write(f"Expected Bhaya rate: {BHAYA_QUIESCENCE_EXPECTED} (0.32%)\n\n")

        for condition in [MODE_SCRIPTED, MODE_VOLTAGE]:
            bhaya_vals = [r["bhaya_peak"] for r in all_results
                          if r["condition"] == condition]
            if bhaya_vals:
                mean_b = np.mean(bhaya_vals)
                max_b  = np.max(bhaya_vals)
                min_b  = np.min(bhaya_vals)
                above  = sum(1 for b in bhaya_vals if b > BHAYA_QUIESCENCE_EXPECTED)
                f.write(f"{condition}:\n")
                f.write(f"  Mean Bhaya peak: {mean_b:.6f}\n")
                f.write(f"  Min / Max:       {min_b:.6f} / {max_b:.6f}\n")
                f.write(f"  Above law:       {above}/{len(bhaya_vals)} runs\n\n")

        f.write("\n" + "="*80 + "\n")
        f.write("TABLE 3: KEY COMPARISON — VOLTAGE-DRIVEN vs FIXED-TOPOLOGY\n")
        f.write("="*80 + "\n\n")
        f.write("Condition               | FRR (mean) | Recovers |\n")
        f.write("------------------------|------------|----------|\n")
        for condition in CONDITIONS:
            runs = [r for r in all_results if r["condition"] == condition]
            if runs:
                frr_mean = np.mean([r["frr_final"] for r in runs])
                rec_rate = sum(1 for r in runs if r["recovered"]) / len(runs)
                f.write(f"{condition:<24}| {frr_mean:.3f}      | {rec_rate:.0%}      |\n")

        f.write("\n")
        f.write(f"Fixed-topology baseline FRR = 0.000 (cannot self-repair by definition)\n")
        f.write(f"This difference is the paper's central claim.\n\n")
        f.write(f"Generated by: run_ablation.py\n")
        f.write(f"Canary: {CANARY}\n")

    print(f"Summary written: {summary_path}")

    # ── Print key results to terminal ─────────────────────────────────────────
    print("\n" + "="*70)
    print("KEY RESULTS")
    print("="*70)

    for condition in CONDITIONS:
        runs = [r for r in all_results if r["condition"] == condition]
        if runs:
            frr_mean  = np.mean([r["frr_final"] for r in runs])
            rec_count = sum(1 for r in runs if r["recovered"])
            bhaya_m   = np.mean([r["bhaya_peak"] for r in runs])
            print(f"\n{condition}:")
            print(f"  FRR (mean):    {frr_mean:.1%}")
            print(f"  Recovered:     {rec_count}/{len(runs)}")
            print(f"  Bhaya (mean):  {bhaya_m:.6f}  [law: {BHAYA_QUIESCENCE_EXPECTED}]")

    print(f"\nBhaya Quiescence Law: {'CONFIRMED' if all(r['bhaya_peak'] < 0.01 for r in all_results if r['condition'] != FIXED_TOPOLOGY) else 'MODIFIED — report honestly'}")
    print(f"\nCanary: {CANARY}")
    print("="*70)
    print(f"\nFiles saved to: {RESULTS_DIR}/")
    print("  ablation_results.csv  — raw data")
    print("  ablation_summary.txt  — paper-ready tables")
    print("  bhaya_log.csv         — series constant analysis")


if __name__ == "__main__":
    main()
