"""
run_visualizer.py
=================
Maya-Morphe Paper 1 — Live PyGame Visualizer
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

Renders the morphogenetic simulation live — direct from Python state.
No translation layer. What you see IS the experiment.

Controls:
  SPACE       Pause / Resume
  D           Apply damage (fraction set by slider logic — default 30%)
  R           Reset everything
  +/-         Speed up / slow down
  1/2/3/4     Set damage fraction (10% / 30% / 50% / 70%)
  Q / ESC     Quit

Run from Maya-Morphe-P1 root:
    python experiments/run_visualizer.py
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify_provenance
verify_provenance.stamp()

# ── Check pygame ──────────────────────────────────────────────────────────────
try:
    import pygame
    import pygame.font
except ImportError:
    print("\n[ERROR] pygame not installed.")
    print("Install with:  pip install pygame")
    sys.exit(1)

import numpy as np
import networkx as nx

from src.morphe.grid import build_grid, remove_nodes, get_voltage_matrix, count_alive, count_edges
from src.morphe.voltage import inject_voltage, diffuse_voltage, measure_bhaya, measure_buddhi
from src.morphe.topology import update_topology, compute_frr
from src.morphe.prana import PranaEngine
from src.morphe.constants import (
    GRID_ROWS, GRID_COLS,
    VAIRAGYA_DECAY_RATE, PRANA_COST_RATE,
    BHAYA_QUIESCENCE_EXPECTED, CANARY
)

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

WIN_W       = 1280
WIN_H       = 780
SIDEBAR_W   = 340
GRID_AREA_W = WIN_W - SIDEBAR_W
GRID_AREA_H = WIN_H
CELL_PAD    = 4   # pixels between cells

# Compute cell size to fill the grid area
CELL_W = (GRID_AREA_W - CELL_PAD) // COLS if (COLS := GRID_COLS) else 28
CELL_H = (GRID_AREA_H - CELL_PAD) // ROWS if (ROWS := GRID_ROWS) else 28
CELL_SIZE = min(CELL_W, CELL_H, 32)
GRID_OFFSET_X = SIDEBAR_W + (GRID_AREA_W - COLS * CELL_SIZE) // 2
GRID_OFFSET_Y = (GRID_AREA_H - ROWS * CELL_SIZE) // 2

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  (matches the HTML dark theme)
# ─────────────────────────────────────────────────────────────────────────────

BG          = (10,  10,  15)
SURFACE     = (18,  18,  26)
SURFACE2    = (26,  26,  46)
BORDER      = (42,  42,  62)
TEAL        = (0,   212, 170)
TEAL_DIM    = (0,   120, 100)
TEAL_DARK   = (0,   40,  34)
GOLD        = (255, 215, 0)
GOLD_DIM    = (180, 140, 0)
RED         = (255, 60,  60)
RED_DARK    = (60,  0,   0)
WHITE       = (232, 232, 240)
GREY        = (120, 120, 160)
BLACK       = (0,   0,   0)
GREEN_HI    = (0,   255, 180)

# ─────────────────────────────────────────────────────────────────────────────
# VOLTAGE → COLOUR  (same formula as HTML version, but correct)
# ─────────────────────────────────────────────────────────────────────────────

def voltage_to_rgb(v: float, alive: bool) -> tuple:
    if not alive:
        return RED_DARK
    v = max(0.0, min(1.0, v))
    t = v ** 0.6
    r = int(0)
    g = int(34  + t * (212 - 34))
    b = int(34  + t * (170 - 34))
    return (r, g, b)

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION STATE
# ─────────────────────────────────────────────────────────────────────────────

class MorpheState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.G           = build_grid()
        self.G_original  = self.G.copy()
        self.prana       = PranaEngine()
        self.timestep    = 0
        self.phase       = "intact"   # intact | running | damaged | recovering
        self.damaged     = False
        self.edges_at_damage = 0
        self.frr         = None
        self.bhaya       = 0.0
        self.buddhi      = 0.030
        self.total_cost  = 0.0
        self.damage_frac = 0.30
        self.speed       = 5          # ticks per frame
        self.paused      = False
        self.log         = [
            f"[init] Maya-Morphe grid ready — {ROWS}×{COLS} cells",
            f"[init] {CANARY}",
            f"[init] VAIRAGYA_DECAY = {VAIRAGYA_DECAY_RATE}",
            "[ctrl] SPACE=pause  D=damage  R=reset  +/-=speed  1-4=damage%  Q=quit",
        ]
        # Inject voltage immediately so grid is alive from frame 1
        sources = self._source_nodes()
        self.G = inject_voltage(self.G, sources, strength=1.0)
        self.phase = "running"

    def _source_nodes(self):
        """Inject at centre + ring of points for broad initial spread."""
        cr, cc = ROWS // 2, COLS // 2
        sources = [(cr, cc)]
        for dr in [-ROWS//4, 0, ROWS//4]:
            for dc in [-COLS//4, 0, COLS//4]:
                r, c = cr + dr, cc + dc
                if 0 <= r < ROWS and 0 <= c < COLS:
                    sources.append((r, c))
        return sources

    def tick(self):
        if self.paused:
            return
        for _ in range(self.speed):
            self.timestep += 1
            self.G, cost = diffuse_voltage(self.G)
            self.prana.consume(cost)
            self.total_cost += cost

            # Re-inject every 30 ticks to keep field alive
            if self.timestep % 30 == 0:
                sources = self._source_nodes()
                self.G = inject_voltage(self.G, sources, strength=0.8)

            self.G, added, pruned = update_topology(self.G)
            self.bhaya   = measure_bhaya(self.G)
            self.buddhi  = measure_buddhi(self.timestep, 200)

            if self.damaged:
                self.frr = compute_frr(self.G_original, self.G)
                if self.frr is not None and self.frr > 0.0:
                    self.phase = "recovering"

    def apply_damage(self):
        if self.damaged:
            return
        self.edges_at_damage = count_edges(self.G)
        self.G_original = self.G.copy()
        self.G, removed = remove_nodes(self.G, fraction=self.damage_frac, seed=42)
        self.G, _, _ = update_topology(self.G)
        self.damaged = True
        self.phase   = "damaged"
        n = len(removed)
        self.log.append(
            f"[t={self.timestep}] DAMAGE: {n} cells removed "
            f"({int(self.damage_frac*100)}%) — watching FRR..."
        )

    def set_damage_frac(self, frac):
        self.damage_frac = frac
        self.log.append(f"[ctrl] Damage fraction → {int(frac*100)}%")

    def change_speed(self, delta):
        self.speed = max(1, min(20, self.speed + delta))
        self.log.append(f"[ctrl] Speed → {self.speed} ticks/frame")

    def add_log(self, msg):
        self.log.append(msg)
        if len(self.log) > 200:
            self.log = self.log[-200:]

# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def draw_rect_border(surf, colour, rect, radius=4, width=1):
    pygame.draw.rect(surf, colour, rect, width, border_radius=radius)

def draw_rect_fill(surf, colour, rect, radius=4):
    pygame.draw.rect(surf, colour, rect, 0, border_radius=radius)

def draw_text(surf, text, font, colour, x, y, align="left"):
    s = font.render(text, True, colour)
    r = s.get_rect()
    if align == "left":   r.topleft  = (x, y)
    elif align == "right":r.topright = (x, y)
    elif align == "center":r.midtop  = (x, y)
    surf.blit(s, r)
    return r.height

def draw_bar(surf, x, y, w, h, value, colour, bg=BORDER, radius=3):
    draw_rect_fill(surf, bg,     pygame.Rect(x, y, w, h), radius)
    fill_w = int(w * max(0.0, min(1.0, value)))
    if fill_w > 0:
        draw_rect_fill(surf, colour, pygame.Rect(x, y, fill_w, h), radius)

def draw_panel(surf, x, y, w, h, radius=8):
    draw_rect_fill(surf, SURFACE2, pygame.Rect(x, y, w, h), radius)
    draw_rect_border(surf, BORDER, pygame.Rect(x, y, w, h), radius)

# ─────────────────────────────────────────────────────────────────────────────
# GRID RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_grid(surf, state: MorpheState, font_tiny):
    G = state.G

    # Draw cell backgrounds
    for r in range(ROWS):
        for c in range(COLS):
            node = (r, c)
            alive = G.nodes[node]["alive"]
            v     = G.nodes[node]["voltage"]
            colour = voltage_to_rgb(v, alive)
            rect = pygame.Rect(
                GRID_OFFSET_X + c * CELL_SIZE + 1,
                GRID_OFFSET_Y + r * CELL_SIZE + 1,
                CELL_SIZE - 2,
                CELL_SIZE - 2
            )
            draw_rect_fill(surf, colour, rect, radius=2)

            # Dead cell — red border
            if not alive:
                draw_rect_border(surf, (120, 0, 0), rect, radius=2, width=1)

            # High voltage glow
            if alive and v > 0.75:
                glow = pygame.Surface((CELL_SIZE - 2, CELL_SIZE - 2), pygame.SRCALPHA)
                alpha = int((v - 0.75) / 0.25 * 80)
                glow.fill((0, 255, 180, alpha))
                surf.blit(glow, rect.topleft)

    # Draw edges (gold, semi-transparent)
    edge_surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    for u, v_node in G.edges():
        r1, c1 = u
        r2, c2 = v_node
        if not G.nodes[u]["alive"] or not G.nodes[v_node]["alive"]:
            continue
        # Colour edge by average voltage
        avg_v = (G.nodes[u]["voltage"] + G.nodes[v_node]["voltage"]) / 2
        alpha = int(40 + avg_v * 140)
        x1 = GRID_OFFSET_X + c1 * CELL_SIZE + CELL_SIZE // 2
        y1 = GRID_OFFSET_Y + r1 * CELL_SIZE + CELL_SIZE // 2
        x2 = GRID_OFFSET_X + c2 * CELL_SIZE + CELL_SIZE // 2
        y2 = GRID_OFFSET_Y + r2 * CELL_SIZE + CELL_SIZE // 2
        pygame.draw.line(edge_surf, (255, 215, 0, alpha), (x1, y1), (x2, y2), 1)
    surf.blit(edge_surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar(surf, state: MorpheState, fonts):
    f_title  = fonts["title"]
    f_body   = fonts["body"]
    f_small  = fonts["small"]
    f_mono   = fonts["mono"]
    f_large  = fonts["large"]

    # Sidebar background
    draw_rect_fill(surf, SURFACE, pygame.Rect(0, 0, SIDEBAR_W, WIN_H))
    draw_rect_border(surf, BORDER, pygame.Rect(0, 0, SIDEBAR_W, WIN_H), radius=0)

    px = 16  # padding x
    py = 14  # running y cursor

    # ── Header ────────────────────────────────────────────────────────────────
    draw_text(surf, "Maya-Morphe", f_large, TEAL, px, py)
    py += 28
    draw_text(surf, "Morphogenetic Computing Visualizer", f_small, GREY, px, py)
    py += 16
    draw_text(surf, "Nexus Learning Labs · Series 3", f_small, GREY, px, py)
    py += 20
    pygame.draw.line(surf, BORDER, (px, py), (SIDEBAR_W - px, py))
    py += 12

    # ── Phase ─────────────────────────────────────────────────────────────────
    phase_colours = {
        "intact":    TEAL,
        "running":   TEAL,
        "damaged":   RED,
        "recovering": GOLD,
    }
    phase_labels = {
        "intact":    "INTACT",
        "running":   "RUNNING",
        "damaged":   "DAMAGED",
        "recovering": "RECOVERING",
    }
    pcol  = phase_colours.get(state.phase, WHITE)
    plbl  = phase_labels.get(state.phase, state.phase.upper())

    draw_panel(surf, px, py, SIDEBAR_W - px*2, 48, radius=8)
    draw_text(surf, plbl, f_title, pcol, px + 12, py + 8)
    draw_text(surf, f"t = {state.timestep}", f_mono, GREY, SIDEBAR_W - px - 10, py + 14, align="right")
    py += 58

    # ── Grid stats ────────────────────────────────────────────────────────────
    draw_panel(surf, px, py, SIDEBAR_W - px*2, 80, radius=8)
    panel_py = py + 10

    alive_count = count_alive(state.G)
    edge_count  = count_edges(state.G)

    draw_text(surf, "Alive cells", f_small, GREY, px + 12, panel_py)
    draw_text(surf, f"{alive_count} / {ROWS*COLS}", f_body, TEAL, SIDEBAR_W - px - 10, panel_py, align="right")
    panel_py += 20
    pygame.draw.line(surf, BORDER, (px + 8, panel_py), (SIDEBAR_W - px - 8, panel_py))
    panel_py += 8

    draw_text(surf, "Active connections", f_small, GREY, px + 12, panel_py)
    draw_text(surf, str(edge_count), f_body, WHITE, SIDEBAR_W - px - 10, panel_py, align="right")
    panel_py += 20
    pygame.draw.line(surf, BORDER, (px + 8, panel_py), (SIDEBAR_W - px - 8, panel_py))
    panel_py += 8

    draw_text(surf, "Speed", f_small, GREY, px + 12, panel_py)
    draw_text(surf, f"{state.speed} ticks/frame", f_body, GREY, SIDEBAR_W - px - 10, panel_py, align="right")
    py += 90

    # ── Antahkarana signals ───────────────────────────────────────────────────
    draw_text(surf, "ANTAHKARANA SIGNALS", f_small, TEAL, px, py)
    py += 14
    draw_panel(surf, px, py, SIDEBAR_W - px*2, 150, radius=8)
    ap = py + 10

    # Vairagya
    draw_text(surf, "Vairagya — Gradient Decay", f_small, GREY, px + 12, ap)
    draw_text(surf, f"{VAIRAGYA_DECAY_RATE:.6f}", f_mono, WHITE, SIDEBAR_W - px - 10, ap, align="right")
    ap += 16
    draw_text(surf, "वैराग्य · Release · ORCID magic", f_small, TEAL_DIM, px + 12, ap)
    ap += 16
    draw_bar(surf, px + 12, ap, SIDEBAR_W - px*2 - 24, 5, VAIRAGYA_DECAY_RATE * 100, TEAL)
    ap += 14

    pygame.draw.line(surf, BORDER, (px + 8, ap), (SIDEBAR_W - px - 8, ap))
    ap += 8

    # Prana
    draw_text(surf, "Prana — Energy Budget", f_small, GREY, px + 12, ap)
    prana_col = TEAL if state.prana.budget > 0.5 else GOLD if state.prana.budget > 0.2 else RED
    draw_text(surf, f"{state.prana.budget:.3f}", f_mono, prana_col, SIDEBAR_W - px - 10, ap, align="right")
    ap += 16
    draw_text(surf, "प्राण · Life Force", f_small, TEAL_DIM, px + 12, ap)
    ap += 14
    draw_bar(surf, px + 12, ap, SIDEBAR_W - px*2 - 24, 5, state.prana.budget, GOLD)
    ap += 14

    py += 160

    # ── Series constants ──────────────────────────────────────────────────────
    draw_text(surf, "SERIES CONSTANTS", f_small, TEAL, px, py)
    py += 14
    draw_panel(surf, px, py, SIDEBAR_W - px*2, 110, radius=8)
    sp = py + 10

    # Bhaya
    draw_text(surf, "Bhaya — Crisis Fraction", f_small, GREY, px + 12, sp)
    bhaya_col = RED if state.bhaya > BHAYA_QUIESCENCE_EXPECTED * 2 else TEAL
    draw_text(surf, f"{state.bhaya:.6f}", f_mono, bhaya_col, SIDEBAR_W - px - 10, sp, align="right")
    sp += 14
    draw_text(surf, f"भय · Law: {BHAYA_QUIESCENCE_EXPECTED:.4f} expected", f_small, TEAL_DIM, px + 12, sp)
    sp += 14
    draw_bar(surf, px + 12, sp, SIDEBAR_W - px*2 - 24, 5, min(state.bhaya / 0.01, 1.0), RED)
    sp += 14

    pygame.draw.line(surf, BORDER, (px + 8, sp), (SIDEBAR_W - px - 8, sp))
    sp += 8

    # Buddhi
    draw_text(surf, "Buddhi — Consolidation", f_small, GREY, px + 12, sp)
    draw_text(surf, f"{state.buddhi:.4f}", f_mono, TEAL, SIDEBAR_W - px - 10, sp, align="right")
    sp += 14
    draw_text(surf, "बुद्धि · S-curve: 0.030→0.988", f_small, TEAL_DIM, px + 12, sp)
    sp += 14
    draw_bar(surf, px + 12, sp, SIDEBAR_W - px*2 - 24, 5, state.buddhi, TEAL)
    py += 120

    # ── FRR ───────────────────────────────────────────────────────────────────
    draw_text(surf, "FUNCTIONAL RECOVERY RATE", f_small, TEAL, px, py)
    py += 14
    draw_panel(surf, px, py, SIDEBAR_W - px*2, 64, radius=8)
    fp = py + 10

    if state.frr is not None:
        frr_pct = state.frr * 100
        frr_col = TEAL if frr_pct > 10 else GOLD if frr_pct > 0 else RED
        draw_text(surf, f"{frr_pct:.1f}%", f_large, frr_col, px + 12, fp)
        draw_text(surf, "Fixed baseline = 0.0%", f_small, GREY, px + 12, fp + 26)
        draw_bar(surf, px + 12, fp + 18, SIDEBAR_W - px*2 - 24, 6, state.frr, frr_col)
    else:
        draw_text(surf, "—", f_large, GREY, px + 12, fp)
        draw_text(surf, "Apply damage first (press D)", f_small, GREY, px + 12, fp + 26)
    py += 74

    # ── Controls hint ─────────────────────────────────────────────────────────
    draw_panel(surf, px, py, SIDEBAR_W - px*2, 78, radius=8)
    cp = py + 8
    hints = [
        ("SPACE", "Pause / Resume"),
        ("D",     f"Apply damage ({int(state.damage_frac*100)}%)"),
        ("R",     "Reset"),
        ("+/-",   f"Speed ({state.speed})"),
        ("1/2/3/4","Damage 10/30/50/70%"),
    ]
    for key, desc in hints:
        draw_text(surf, key, f_mono,  GOLD,  px + 12,  cp)
        draw_text(surf, desc, f_small, GREY, px + 55, cp)
        cp += 13
    py += 88

    # ── Log ───────────────────────────────────────────────────────────────────
    log_h = WIN_H - py - 10
    if log_h > 40:
        draw_panel(surf, px, py, SIDEBAR_W - px*2, log_h, radius=8)
        lp = py + 6
        visible = max(1, (log_h - 12) // 13)
        for line in state.log[-visible:]:
            if lp + 13 > py + log_h:
                break
            col = TEAL if line.startswith("[init]") else \
                  RED  if "DAMAGE" in line else \
                  GOLD if "FRR" in line else \
                  GREY
            # Truncate long lines
            if len(line) > 44:
                line = line[:43] + "…"
            draw_text(surf, line, f_small, col, px + 8, lp)
            lp += 13

# ─────────────────────────────────────────────────────────────────────────────
# OVERLAY: PAUSED
# ─────────────────────────────────────────────────────────────────────────────

def render_pause_overlay(surf, fonts):
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 100))
    surf.blit(overlay, (0, 0))
    cx = SIDEBAR_W + GRID_AREA_W // 2
    cy = WIN_H // 2
    draw_text(surf, "PAUSED", fonts["huge"], GOLD, cx, cy - 20, align="center")
    draw_text(surf, "Press SPACE to resume", fonts["body"], GREY, cx, cy + 20, align="center")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    pygame.display.set_caption("Maya-Morphe — Morphogenetic Computing Visualizer | Nexus Learning Labs")

    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    clock  = pygame.time.Clock()

    # Fonts — system fallbacks, no external files needed
    def make_font(size, bold=False):
        for name in ["Segoe UI", "Arial", "Helvetica", "DejaVu Sans", ""]:
            try:
                return pygame.font.SysFont(name, size, bold=bold)
            except:
                pass
        return pygame.font.Font(None, size)

    def make_mono(size):
        for name in ["Consolas", "Courier New", "Lucida Console", "DejaVu Sans Mono", ""]:
            try:
                return pygame.font.SysFont(name, size)
            except:
                pass
        return pygame.font.Font(None, size)

    fonts = {
        "huge":  make_font(36, bold=True),
        "large": make_font(20, bold=True),
        "title": make_font(16, bold=True),
        "body":  make_font(14),
        "small": make_font(12),
        "tiny":  make_font(10),
        "mono":  make_mono(12),
    }

    state = MorpheState()
    state.add_log("[viz] PyGame visualizer started")
    state.add_log(f"[viz] Grid: {ROWS}×{COLS} | {ROWS*COLS} cells")
    state.add_log("[viz] Voltage injecting — watch the field spread")

    running = True
    frame   = 0

    while running:
        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key

                if k in (pygame.K_q, pygame.K_ESCAPE):
                    running = False

                elif k == pygame.K_SPACE:
                    state.paused = not state.paused
                    state.add_log("[ctrl] " + ("Paused" if state.paused else "Resumed"))

                elif k == pygame.K_d:
                    if not state.damaged:
                        state.apply_damage()
                    else:
                        state.add_log("[ctrl] Damage already applied — press R to reset")

                elif k == pygame.K_r:
                    state.reset()
                    state.add_log("[reset] Grid reset. Ready.")

                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    state.change_speed(+2)

                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    state.change_speed(-2)

                elif k == pygame.K_1:
                    state.set_damage_frac(0.10)
                elif k == pygame.K_2:
                    state.set_damage_frac(0.30)
                elif k == pygame.K_3:
                    state.set_damage_frac(0.50)
                elif k == pygame.K_4:
                    state.set_damage_frac(0.70)

        # ── Simulation tick ───────────────────────────────────────────────────
        state.tick()

        # Log FRR every 50 ticks after damage
        if state.damaged and state.timestep % 50 == 0 and state.frr is not None:
            state.add_log(
                f"[t={state.timestep}] edges={count_edges(state.G)} "
                f"FRR={state.frr*100:.1f}% "
                f"bhaya={state.bhaya:.5f} "
                f"buddhi={state.buddhi:.3f}"
            )

        # ── Render ────────────────────────────────────────────────────────────
        screen.fill(BG)

        # Grid background
        pygame.draw.rect(screen, SURFACE, pygame.Rect(SIDEBAR_W, 0, GRID_AREA_W, WIN_H))

        # Grid divider line
        pygame.draw.line(screen, BORDER, (SIDEBAR_W, 0), (SIDEBAR_W, WIN_H), 1)

        render_grid(screen, state, fonts["tiny"])
        render_sidebar(screen, state, fonts)

        if state.paused:
            render_pause_overlay(screen, fonts)

        # Grid label top-right
        label = f"{ROWS}×{COLS}  ·  {count_alive(state.G)} alive  ·  {count_edges(state.G)} edges"
        draw_text(screen, label, fonts["small"], GREY,
                  WIN_W - 16, 10, align="right")

        pygame.display.flip()
        clock.tick(30)   # 30 fps cap
        frame += 1

    pygame.quit()
    print(f"\n[done] Simulation ended at t={state.timestep}")
    print(f"[done] Bhaya: {state.bhaya:.6f} | Buddhi: {state.buddhi:.4f}")
    if state.frr is not None:
        print(f"[done] Final FRR: {state.frr*100:.1f}%")
    print(f"[done] {CANARY}")


if __name__ == "__main__":
    main()
