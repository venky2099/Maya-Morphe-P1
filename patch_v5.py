"""
patch_v5.py
===========
Run this once to fix Mode 3 stalling issue.
Maya-Morphe | Nexus Learning Labs
"""
import os

# ── Patch 1: voltage.py ───────────────────────────────────────────────────────
vpath = os.path.join("src", "morphe", "voltage.py")
with open(vpath, "r", encoding="utf-8") as f:
    v = f.read()

v = v.replace("GROWING_CELL_EMIT_VOLTAGE = 0.80",
              "GROWING_CELL_EMIT_VOLTAGE = 0.95")
v = v.replace("REGROWTH_VOLTAGE_THRESHOLD_M3 = 0.10",
              "REGROWTH_VOLTAGE_THRESHOLD_M3 = 0.08")

with open(vpath, "w", encoding="utf-8") as f:
    f.write(v)
print("[1] voltage.py patched: emit=0.95  threshold_m3=0.08")

# ── Patch 2: run_lizard_v5.py ─────────────────────────────────────────────────
lpath = os.path.join("experiments", "run_lizard_v5.py")
with open(lpath, "r", encoding="utf-8") as f:
    l = f.read()

OLD = (
    "# Wound voltage gradually decays back to resting\n"
    "                if (self.regrowth_active\n"
    "                        and cell.region == \"TAIL\"\n"
    "                        and cell.current_voltage > cell.base_voltage + 0.1):\n"
    "                    cell.current_voltage -= wound_decay * dt"
)
NEW = (
    "# Wound voltage decays only in Mode 1/2 — Mode 3 keeps stump hot\n"
    "                if (self.regrowth_active\n"
    "                        and cell.region == \"TAIL\"\n"
    "                        and self.mode != MODE_PROPAGATING\n"
    "                        and cell.current_voltage > cell.base_voltage + 0.1):\n"
    "                    cell.current_voltage -= wound_decay * dt"
)

if OLD in l:
    l = l.replace(OLD, NEW)
    with open(lpath, "w", encoding="utf-8") as f:
        f.write(l)
    print("[2] run_lizard_v5.py patched: wound decay disabled for Mode 3")
else:
    print("[2] WARN: pattern not found — may already be patched")

print("\nDone. Run: python experiments/run_lizard_v5.py")
