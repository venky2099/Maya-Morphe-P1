"""
run_smoke_test.py
=================
Maya-Morphe Paper 1 — Smoke Test
Nexus Learning Labs | ORCID: 0000-0002-3315-7907

Verifies the full stack is operational:
  1. Provenance check
  2. Grid construction
  3. Voltage injection and diffusion (5 timesteps)
  4. Topology update
  5. Prana engine
  6. Bhaya + Buddhi series constant measurement
  7. BETSE import check
  8. HTML visualizer generation

Run from Maya-Morphe-P1 root:
    python experiments/run_smoke_test.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify_provenance
verify_provenance.stamp()

print("\n" + "="*60)
print("MAYA-MORPHE SMOKE TEST")
print("Nexus Learning Labs | ORCID: 0000-0002-3315-7907")
print("="*60)

# ── 1. Grid ───────────────────────────────────────────────────────────────────
print("\n[1] Building 20x20 cell grid...")
from src.morphe.grid import build_grid, remove_nodes, get_voltage_matrix, count_alive, count_edges
from src.morphe.constants import GRID_ROWS, GRID_COLS

G = build_grid()
print(f"    Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()} | Alive: {count_alive(G)}")
assert G.number_of_nodes() == GRID_ROWS * GRID_COLS, "Grid node count mismatch"
print("    [PASS]")

# ── 2. Voltage injection ──────────────────────────────────────────────────────
print("\n[2] Injecting voltage at grid centre...")
from src.morphe.voltage import inject_voltage, diffuse_voltage, measure_bhaya, measure_buddhi

centre = (GRID_ROWS // 2, GRID_COLS // 2)
G = inject_voltage(G, [centre], strength=1.0)
assert G.nodes[centre]["voltage"] == 1.0, "Voltage injection failed"
print(f"    Centre voltage: {G.nodes[centre]['voltage']:.4f}")
print("    [PASS]")

# ── 3. Diffusion ──────────────────────────────────────────────────────────────
print("\n[3] Running 5 diffusion timesteps...")
from src.morphe.prana import PranaEngine
prana = PranaEngine()
total_cost = 0.0
for t in range(5):
    G, cost = diffuse_voltage(G)
    prana.consume(cost)
    total_cost += cost
    print(f"    t={t+1} | centre_v={G.nodes[centre]['voltage']:.4f} | prana={prana.budget:.4f} | cost={cost:.6f}")
print("    [PASS]")

# ── 4. Topology update ────────────────────────────────────────────────────────
print("\n[4] Running topology update...")
from src.morphe.topology import update_topology
G, added, pruned = update_topology(G)
print(f"    Edges after update: {count_edges(G)} | Added: {added} | Pruned: {pruned}")
print("    [PASS]")

# ── 5. Node removal ───────────────────────────────────────────────────────────
print("\n[5] Removing 30% of nodes (damage test)...")
G_damaged, removed = remove_nodes(G, fraction=0.3, seed=42)
alive_after = count_alive(G_damaged)
print(f"    Removed: {len(removed)} nodes | Alive: {alive_after}/{G.number_of_nodes()}")
print("    [PASS]")

# ── 6. Series constants ───────────────────────────────────────────────────────
print("\n[6] Series constants check...")
bhaya = measure_bhaya(G_damaged)
buddhi = measure_buddhi(timestep=50, total_timesteps=100)
print(f"    Bhaya (crisis fraction): {bhaya:.6f}  [expected ~0.0032 if law holds]")
print(f"    Buddhi S-curve at t=50%: {buddhi:.4f}  [expected ~0.500]")
print("    [PASS — values recorded, not asserted — genuine research]")

# ── 7. BETSE import ───────────────────────────────────────────────────────────
print("\n[7] BETSE import check...")
try:
    import betse
    print(f"    BETSE version: {betse.__version__}")
    print("    [PASS]")
except ImportError:
    print("    [WARN] BETSE not installed yet.")
    print("    Install with: pip install betse")
    print("    Continuing — core morphe stack is independent of BETSE for smoke test.")

# ── 8. Visualizer generation ──────────────────────────────────────────────────
print("\n[8] Generating HTML visualizer...")
import json
import numpy as np
from src.morphe.grid import get_voltage_matrix

voltage_matrix = get_voltage_matrix(G_damaged)
voltage_list = voltage_matrix.tolist()

# Collect alive/dead node info
alive_matrix = [[G_damaged.nodes[(r,c)]["alive"] for c in range(GRID_COLS)] for r in range(GRID_ROWS)]

snapshot_data = {
    "rows": GRID_ROWS,
    "cols": GRID_COLS,
    "voltage": voltage_list,
    "alive": alive_matrix,
    "bhaya": round(bhaya, 6),
    "buddhi": round(buddhi, 4),
    "prana": round(prana.budget, 4),
    "edges": count_edges(G_damaged),
    "alive_count": count_alive(G_damaged),
    "removed_count": len(removed)
}

# Write visualizer
viz_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visualizer", "index.html")
os.makedirs(os.path.dirname(viz_path), exist_ok=True)

# Read template and inject data
template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visualizer", "template.html")
if os.path.exists(template_path):
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__SNAPSHOT_DATA__", json.dumps(snapshot_data))
    with open(viz_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"    Visualizer written: visualizer/index.html")
    print("    Open in browser to see the cell grid.")
else:
    print("    [WARN] template.html not found — run bootstrap again.")

print("\n" + "="*60)
print("SMOKE TEST COMPLETE")
print("="*60)
print(f"  Grid: {GRID_ROWS}x{GRID_COLS} | Nodes: {G.number_of_nodes()}")
print(f"  Damage: 30% | Alive after: {alive_after}")
print(f"  Bhaya: {bhaya:.6f} | Buddhi: {buddhi:.4f} | Prana: {prana.budget:.4f}")
print(f"  Canary: MayaNexusVS2026NLL_Bengaluru_Narasimha")
print("="*60)
