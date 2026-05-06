"""
patch_v5b.py
============
Fixes two bugs in run_lizard_v5.py:

BUG 1: Stump cells lose wound voltage immediately because
        ambient pulse overwrites current_voltage every tick.
        Fix: raise base_voltage permanently for stump cells on cut.

BUG 2: Some tail tip cells survive amputation because the
        cut boundary only checks cell.y > cut_y, missing cells
        that are in the TAIL region but have irregular y positions.
        Fix: kill ALL tail cells below cut_y using region check too.

Maya-Morphe | Nexus Learning Labs | ORCID: 0000-0002-3315-7907
"""
import os
import re

path = os.path.join("experiments", "run_lizard_v5.py")
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# ── BUG 1: stump base_voltage elevation ───────────────────────────────────────
OLD1 = (
    "        # Wound flare\n"
    "        for c in tail:\n"
    "            if c.y <= self.cut_y:\n"
    "                c.current_voltage = 1.0"
)
NEW1 = (
    "        # Wound flare + permanent base elevation for stump cells\n"
    "        # base_voltage raised so ambient pulse keeps stump hot throughout\n"
    "        for c in tail:\n"
    "            if c.y <= self.cut_y:\n"
    "                c.base_voltage = 0.78   # elevated wound potential\n"
    "                c.current_voltage = 1.0  # initial flare"
)

if OLD1 in src:
    src = src.replace(OLD1, NEW1)
    print("[1] Stump base_voltage elevation patched")
else:
    print("[1] WARN: stump pattern not found — check manually")

# ── BUG 2: kill ALL tail cells below cut, not just by y position ──────────────
OLD2 = (
    "        severed = sorted(\n"
    "            [c for c in tail if c.y > self.cut_y],\n"
    "            key=lambda c: c.y, reverse=True\n"
    "        )"
)
NEW2 = (
    "        # Kill ALL tail cells below cut_y — region check ensures\n"
    "        # no tail cell survives regardless of Poisson position scatter\n"
    "        severed = sorted(\n"
    "            [c for c in self.cells\n"
    "             if c.region == \"TAIL\" and c.y > self.cut_y],\n"
    "            key=lambda c: c.y, reverse=True\n"
    "        )"
)

if OLD2 in src:
    src = src.replace(OLD2, NEW2)
    print("[2] Tail death boundary patched")
else:
    print("[2] WARN: severed pattern not found — check manually")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("\nDone. Run: python experiments/run_lizard_v5.py")
