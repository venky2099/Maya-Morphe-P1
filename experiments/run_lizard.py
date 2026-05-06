"""
run_lizard.py
=============
Maya-Morphe Paper 1 — Procedural Cellular Lizard Visualizer
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

A top-down lizard made entirely of bioelectric cells.
Each cell glows with voltage. The tail gets cut. It grows back.
This IS morphogenetic computing — made visible.

Architecture (from Gemini Deep Research):
  - Silhouette drawn to off-screen surface via primitives + Bezier
  - pygame.mask for O(1) cell packing — pixel-exact, no math overhead
  - Heuristic spatial partitioning for region labels
  - Additive BLEND_RGB_ADD with pre-cached glow surface
  - Time-delta (dt) integration — frame-rate independent animation
  - Procedural CPU vertex shader for organic tail wobble

Controls:
  T           Cut the tail (progressive tip-to-body death)
  R           Reset everything
  +/-         Speed up / slow down ambient pulse
  Q / ESC     Quit

Run from Maya-Morphe-P1 root:
    python experiments/run_lizard.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify_provenance
verify_provenance.stamp()

try:
    import pygame
except ImportError:
    print("\n[ERROR] pygame not installed. Run: pip install pygame")
    sys.exit(1)

from src.morphe.constants import CANARY, VAIRAGYA_DECAY_RATE, BHAYA_QUIESCENCE_EXPECTED

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_WIDTH   = 1280
WINDOW_HEIGHT  = 780
SIDEBAR_WIDTH  = 300
CELL_SIZE      = 14      # pixels per cell — gives ~300 cells in the lizard
MARGIN         = 2       # gap between cells — makes scales visible

# Colour palette
BG_COLOR       = (10,  10,  15)
SIDEBAR_COLOR  = (18,  18,  26)
BORDER_COLOR   = (42,  42,  62)
TEAL           = (0,   212, 170)
GOLD           = (255, 215, 0)
RED_DARK       = (40,  0,   0)
RED_BORDER     = (200, 30,  30)
TEXT_COLOR     = (200, 220, 220)
TEXT_DIM       = (100, 110, 130)
WHITE          = (255, 255, 255)

# Cell states
ALIVE   = 0
DYING   = 1
DEAD    = 2
GROWING = 3

# ─────────────────────────────────────────────────────────────────────────────
# PARTICLE  (kinematic — Euler integration)
# ─────────────────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        angle  = random.uniform(0, math.pi * 2)
        speed  = random.uniform(120, 420)
        self.vx    = math.cos(angle) * speed
        self.vy    = math.sin(angle) * speed
        self.life  = 1.0
        self.size  = random.randint(2, 4)
        self.color = random.choice([(0, 255, 180), (255, 215, 0), (255, 255, 200)])

    def update(self, dt):
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.vx   *= 0.92        # drag
        self.vy   *= 0.92
        self.life -= dt * 2.2
        return self.life > 0

# ─────────────────────────────────────────────────────────────────────────────
# CELL
# ─────────────────────────────────────────────────────────────────────────────

class Cell:
    def __init__(self, x, y, region):
        self.base_x   = float(x)
        self.base_y   = float(y)
        self.render_x = float(x)
        self.render_y = float(y)
        self.region   = region
        self.state    = ALIVE

        # Slight variation so the lizard looks alive even at rest
        self.base_voltage    = random.uniform(0.35, 0.65)
        self.current_voltage = self.base_voltage
        self.delay_timer     = 0.0
        self.decay_timer     = 0.0

    def get_color(self):
        if self.state == DEAD:
            return RED_DARK

        v = max(0.0, min(1.0, self.current_voltage))

        # Multi-node gradient:
        # 0.0 → dark forest green (resting)
        # 0.5 → bright teal (active)
        # 1.0 → white-hot (peak / wound flare)
        c_rest = (10,  60,  20)
        c_teal = (0,   212, 170)
        c_peak = (255, 255, 255)

        if v < 0.5:
            t = v * 2.0
            r = int(c_rest[0] + (c_teal[0] - c_rest[0]) * t)
            g = int(c_rest[1] + (c_teal[1] - c_rest[1]) * t)
            b = int(c_rest[2] + (c_teal[2] - c_rest[2]) * t)
        else:
            t = (v - 0.5) * 2.0
            r = int(c_teal[0] + (c_peak[0] - c_teal[0]) * t)
            g = int(c_teal[1] + (c_peak[1] - c_teal[1]) * t)
            b = int(c_teal[2] + (c_peak[2] - c_teal[2]) * t)

        return (max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)))

# ─────────────────────────────────────────────────────────────────────────────
# MAIN VISUALIZER
# ─────────────────────────────────────────────────────────────────────────────

class LizardVisualizer:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(
            "Maya-Morphe — Cellular Lizard | Nexus Learning Labs | ORCID: 0000-0002-3315-7907"
        )
        self.clock = pygame.time.Clock()

        # Fonts — no external files needed
        self.font_title  = self._font(18, bold=True)
        self.font_body   = self._font(14)
        self.font_small  = self._font(12)
        self.font_mono   = self._mono(12)
        self.font_large  = self._font(22, bold=True)
        self.font_huge   = self._font(36, bold=True)

        # Viewport centre (lizard is centred here)
        self.cx = SIDEBAR_WIDTH + (WINDOW_WIDTH - SIDEBAR_WIDTH) // 2
        self.cy = WINDOW_HEIGHT // 2 + 30   # slight downward offset so head has room

        # Pre-cache glow surface — drawn ONCE, blitted with BLEND_RGB_ADD
        self.glow_radius = int(CELL_SIZE * 2.8)
        self.glow_surf   = self._precompute_glow(self.glow_radius)

        self.cells     = []
        self.particles = []
        self._build_lizard()

        # Animation state
        self.global_time       = 0.0
        self.amputation_active = False
        self.regrowth_active   = False
        self.cut_y             = None
        self.phase_label       = "INTACT"
        self.frr               = None
        self.bhaya             = 0.0
        self.total_dead        = 0
        self.pulse_speed       = 1.0

        # Log
        self.log = [
            f"[init] {CANARY}",
            f"[init] VAIRAGYA_DECAY = {VAIRAGYA_DECAY_RATE}",
            f"[init] {len(self.cells)} cells packed",
            "[ctrl] T = cut tail   R = reset   Q = quit",
        ]

    # ── Font helpers ──────────────────────────────────────────────────────────

    def _font(self, size, bold=False):
        for name in ["Segoe UI", "Arial", "Helvetica", ""]:
            try: return pygame.font.SysFont(name, size, bold=bold)
            except: pass
        return pygame.font.Font(None, size)

    def _mono(self, size):
        for name in ["Consolas", "Courier New", "Lucida Console", ""]:
            try: return pygame.font.SysFont(name, size)
            except: pass
        return pygame.font.Font(None, size)

    # ── Glow pre-computation ──────────────────────────────────────────────────

    def _precompute_glow(self, radius):
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        cx, cy = radius, radius
        for r in range(radius, 0, -1):
            alpha = int(180 * (1 - (r / radius) ** 2))
            pygame.draw.circle(surf, (0, 180, 140, alpha), (cx, cy), r)
        return surf

    # ── Bezier polygon for tapering tail ──────────────────────────────────────

    def _bezier_polygon(self, p0, p1, p2, w0, w1, segments=24):
        """Quadratic Bezier with variable width — produces a tapered polygon."""
        left, right = [], []
        p0x, p0y = p0
        p1x, p1y = p1
        p2x, p2y = p2
        for i in range(segments + 1):
            t  = i / segments
            # Position on curve (Bernstein)
            bx = (1-t)**2 * p0x + 2*(1-t)*t * p1x + t**2 * p2x
            by = (1-t)**2 * p0y + 2*(1-t)*t * p1y + t**2 * p2y
            # Tangent (derivative)
            tx = 2*(1-t)*(p1x-p0x) + 2*t*(p2x-p1x)
            ty = 2*(1-t)*(p1y-p0y) + 2*t*(p2y-p1y)
            ln = math.hypot(tx, ty) or 0.001
            # Normal (perpendicular to tangent)
            nx, ny = -ty/ln, tx/ln
            w = w0 + (w1 - w0) * t
            left.append( (bx + nx*w, by + ny*w))
            right.append((bx - nx*w, by - ny*w))
        return left + right[::-1]

    # ── Build lizard silhouette + pack cells ──────────────────────────────────

    def _build_lizard(self):
        cx, cy = self.cx, self.cy

        # Draw white silhouette on black off-screen surface
        mask_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        mask_surf.fill((0, 0, 0))
        W = (255, 255, 255)

        # 1. TORSO — elongated ellipse
        pygame.draw.ellipse(mask_surf, W,
            pygame.Rect(cx - 38, cy - 95, 76, 190))

        # 2. HEAD — kite/diamond polygon tapering to snout
        head_pts = [
            (cx - 28, cy - 88),
            (cx + 28, cy - 88),
            (cx + 18, cy - 148),
            (cx,      cy - 172),
            (cx - 18, cy - 148),
        ]
        pygame.draw.polygon(mask_surf, W, head_pts)

        # 3. EYE bumps (just silhouette nubs on head)
        pygame.draw.circle(mask_surf, W, (cx - 14, cy - 130), 8)
        pygame.draw.circle(mask_surf, W, (cx + 14, cy - 130), 8)

        # 4. FRONT LEGS — angled polygons with elbow kink
        # Left front
        pygame.draw.polygon(mask_surf, W, [
            (cx - 28, cy - 60),
            (cx - 28, cy - 35),
            (cx - 55, cy - 20),
            (cx - 90, cy - 30),
            (cx - 88, cy - 50),
            (cx - 58, cy - 48),
        ])
        # Right front
        pygame.draw.polygon(mask_surf, W, [
            (cx + 28, cy - 60),
            (cx + 28, cy - 35),
            (cx + 55, cy - 20),
            (cx + 90, cy - 30),
            (cx + 88, cy - 50),
            (cx + 58, cy - 48),
        ])

        # 5. BACK LEGS — wider, more powerful
        # Left back
        pygame.draw.polygon(mask_surf, W, [
            (cx - 30, cy + 40),
            (cx - 30, cy + 70),
            (cx - 62, cy + 90),
            (cx - 95, cy + 75),
            (cx - 92, cy + 52),
            (cx - 60, cy + 60),
        ])
        # Right back
        pygame.draw.polygon(mask_surf, W, [
            (cx + 30, cy + 40),
            (cx + 30, cy + 70),
            (cx + 62, cy + 90),
            (cx + 95, cy + 75),
            (cx + 92, cy + 52),
            (cx + 60, cy + 60),
        ])

        # 6. TAIL — tapered Bezier curve, slight rightward curve then back
        tail_start = (cx,     cy + 88)
        tail_ctrl  = (cx + 45, cy + 200)
        tail_end   = (cx - 15, cy + 330)
        tail_poly  = self._bezier_polygon(
            tail_start, tail_ctrl, tail_end,
            w0=22, w1=1, segments=30
        )
        pygame.draw.polygon(mask_surf, W, [(int(x), int(y)) for x,y in tail_poly])

        # Convert silhouette to bitmask — O(1) lookup per cell
        self.lizard_mask = pygame.mask.from_surface(mask_surf)

        # Store bounding info for region labelling
        self._body_top    = cy - 95
        self._body_bottom = cy + 88
        self._tail_top    = cy + 88
        self._tail_bottom = cy + 330

        # Pack cells via uniform grid + mask sampling
        self.cells = []
        for py_y in range(0, WINDOW_HEIGHT, CELL_SIZE):
            for px_x in range(SIDEBAR_WIDTH, WINDOW_WIDTH, CELL_SIZE):
                if self.lizard_mask.get_at((px_x, py_y)):
                    region = self._classify(px_x, py_y, cx, cy)
                    self.cells.append(Cell(px_x, py_y, region))

        # Store original tail cell count for FRR
        self._original_tail_count = sum(1 for c in self.cells if c.region == "TAIL")

    def _classify(self, x, y, cx, cy):
        """Heuristic spatial partitioning — bounding box rules."""
        if y < cy - 88:
            return "HEAD"
        elif y > cy + 88:
            return "TAIL"
        elif x < cx - 32:
            return "FRONT_LEG_L" if y < cy else "BACK_LEG_L"
        elif x > cx + 32:
            return "FRONT_LEG_R" if y < cy else "BACK_LEG_R"
        else:
            return "BODY"

    # ── Amputation ────────────────────────────────────────────────────────────

    def _trigger_amputation(self):
        if self.amputation_active:
            self._add_log("[ctrl] Already cut — press R to reset")
            return

        tail_cells = [c for c in self.cells if c.region == "TAIL"]
        if not tail_cells:
            return

        self.amputation_active = True
        self.regrowth_active   = False
        self.phase_label       = "DAMAGED"

        # Cut at 35% down the tail length
        y_min = min(c.base_y for c in tail_cells)
        y_max = max(c.base_y for c in tail_cells)
        self.cut_y = y_min + (y_max - y_min) * 0.35

        # Cells below cut_y are severed — sorted tip-first (highest y first)
        severed = sorted(
            [c for c in tail_cells if c.base_y > self.cut_y],
            key=lambda c: c.base_y, reverse=True
        )

        # Assign progressive death delays — tip dies first, cascades to stump
        for idx, cell in enumerate(severed):
            cell.delay_timer = (idx / max(len(severed), 1)) * 1.2

        # Wound flare — stump cells spike to white-hot
        stump_cells = [c for c in tail_cells if c.base_y <= self.cut_y]
        for cell in stump_cells:
            cell.current_voltage = 1.0

        # Particle burst at cut site
        if stump_cells:
            burst_x = sum(c.base_x for c in stump_cells) / len(stump_cells)
            burst_y = self.cut_y
            for _ in range(45):
                self.particles.append(Particle(burst_x, burst_y))

        self._add_log(
            f"[CUT] {len(severed)} cells severed at y={int(self.cut_y)} — watching FRR..."
        )

    def _trigger_regrowth(self):
        if self.regrowth_active:
            return

        self.regrowth_active = True
        self.phase_label     = "REGROWING"

        dead_tail = sorted(
            [c for c in self.cells if c.region == "TAIL" and c.state == DEAD],
            key=lambda c: c.base_y   # stump-first (lowest y)
        )

        for idx, cell in enumerate(dead_tail):
            cell.delay_timer = (idx / max(len(dead_tail), 1)) * 5.0

        self._add_log(f"[REGROW] {len(dead_tail)} cells regrowing from stump...")

    # ── Update logic (dt-integrated) ─────────────────────────────────────────

    def update(self, dt):
        self.global_time += dt

        self.particles = [p for p in self.particles if p.update(dt)]

        dead_count     = 0
        growing_count  = 0
        alive_tail     = 0

        for cell in self.cells:

            # ── ALIVE: ambient voltage pulse + tail wobble ─────────────────
            if cell.state == ALIVE:
                if cell.region == "TAIL":
                    alive_tail += 1
                # Ambient biological pulse — each cell oscillates slightly
                pulse = math.sin(
                    self.global_time * 1.8 * self.pulse_speed
                    + cell.base_y * 0.04
                    + cell.base_x * 0.02
                ) * 0.12
                cell.current_voltage = cell.base_voltage + pulse

                # Tail wobble — CPU vertex shader (Gemini technique)
                if cell.region == "TAIL" and self.cut_y is None:
                    amp = (cell.base_y - self.cy) * 0.04
                    cell.render_x = cell.base_x + math.sin(
                        self.global_time * 2.5 + cell.base_y * 0.025
                    ) * amp
                else:
                    cell.render_x = cell.base_x

                # Countdown to death
                if (self.amputation_active
                        and cell.region == "TAIL"
                        and cell.base_y > (self.cut_y or 1e9)
                        and cell.delay_timer > 0):
                    cell.delay_timer -= dt
                    if cell.delay_timer <= 0:
                        cell.state       = DYING
                        cell.decay_timer = 0.18

            # ── DYING: voltage drains to zero ─────────────────────────────
            elif cell.state == DYING:
                cell.current_voltage -= dt * (1.0 / 0.18)
                cell.decay_timer     -= dt
                if cell.decay_timer <= 0:
                    cell.state           = DEAD
                    cell.current_voltage = 0.0
                dead_count += 1

            # ── DEAD: waiting for regrowth signal ─────────────────────────
            elif cell.state == DEAD:
                dead_count += 1
                if self.regrowth_active and cell.delay_timer > 0:
                    cell.delay_timer -= dt
                    if cell.delay_timer <= 0:
                        cell.state           = GROWING
                        cell.current_voltage = 0.05

            # ── GROWING: dims in, tissue maturing ─────────────────────────
            elif cell.state == GROWING:
                growing_count += 1
                cell.current_voltage = min(
                    cell.base_voltage,
                    cell.current_voltage + dt * 0.18
                )
                if cell.current_voltage >= cell.base_voltage * 0.95:
                    cell.state = ALIVE

        self.total_dead = dead_count

        # FRR calculation
        if self.amputation_active and self._original_tail_count > 0:
            self.frr = alive_tail / self._original_tail_count
        else:
            self.frr = None

        # Bhaya — isolated high-voltage cells (series constant test)
        crisis = 0
        alive_total = sum(1 for c in self.cells if c.state == ALIVE)
        # simplified: cells that are alive + voltage > 0.85 (wound flare analog)
        crisis = sum(
            1 for c in self.cells
            if c.state == ALIVE and c.current_voltage > 0.85
        )
        self.bhaya = crisis / max(alive_total, 1)

        # Auto-trigger regrowth once all severed cells are dead
        if (self.amputation_active
                and not self.regrowth_active
                and dead_count > 0
                and all(
                    c.state in (DEAD, ALIVE)
                    for c in self.cells
                    if c.region == "TAIL" and c.base_y > (self.cut_y or 1e9)
                )
                and all(
                    c.state != DYING
                    for c in self.cells
                )):
            self._trigger_regrowth()

        # Recovery complete
        if (self.regrowth_active
                and growing_count == 0
                and dead_count == 0):
            self.amputation_active = False
            self.regrowth_active   = False
            self.cut_y             = None
            self.phase_label       = "RECOVERED"
            self.frr               = None
            self._add_log("[DONE] Tail fully regenerated! FRR = 100%")

    # ── Render ────────────────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(BG_COLOR)

        # Cells — base pass
        cell_inner = CELL_SIZE - MARGIN
        glow_queue = []

        for cell in self.cells:
            rx = int(cell.render_x)
            ry = int(cell.render_y)
            rect = pygame.Rect(rx, ry, cell_inner, cell_inner)

            if cell.state == DEAD:
                pygame.draw.rect(self.screen, RED_DARK,   rect, border_radius=3)
                pygame.draw.rect(self.screen, RED_BORDER, rect, width=1, border_radius=3)
            else:
                color = cell.get_color()
                pygame.draw.rect(self.screen, color, rect, border_radius=3)
                if cell.current_voltage > 0.7:
                    glow_queue.append((rx, ry))

        # Additive glow pass (cached surface — fast)
        gr = self.glow_radius
        for gx, gy in glow_queue:
            pos = (gx - gr + cell_inner // 2, gy - gr + cell_inner // 2)
            self.screen.blit(self.glow_surf, pos,
                             special_flags=pygame.BLEND_RGB_ADD)

        # Cut line indicator
        if self.cut_y is not None:
            cut_yi = int(self.cut_y)
            pygame.draw.line(
                self.screen, (200, 50, 50),
                (SIDEBAR_WIDTH, cut_yi), (WINDOW_WIDTH, cut_yi), 1
            )

        # Particles
        for p in self.particles:
            alpha = max(0, min(255, int(255 * p.life)))
            col   = tuple(min(255, int(c * p.life)) for c in p.color)
            pygame.draw.circle(
                self.screen, col,
                (int(p.x), int(p.y)), p.size
            )

        # Sidebar
        self._draw_sidebar()

        pygame.display.flip()

    def _draw_sidebar(self):
        # Background
        pygame.draw.rect(self.screen, SIDEBAR_COLOR,
                         pygame.Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(self.screen, GOLD,
                         (SIDEBAR_WIDTH, 0), (SIDEBAR_WIDTH, WINDOW_HEIGHT), 2)

        px, py = 16, 14

        # Title
        self._txt("Maya-Morphe", self.font_large, TEAL, px, py)
        py += 26
        self._txt("Morphogenetic Computing", self.font_small, TEXT_DIM, px, py)
        py += 15
        self._txt("Nexus Learning Labs · Series 3", self.font_small, TEXT_DIM, px, py)
        py += 20
        pygame.draw.line(self.screen, BORDER_COLOR,
                         (px, py), (SIDEBAR_WIDTH - px, py))
        py += 12

        # Phase badge
        phase_col = {
            "INTACT":    TEAL,
            "DAMAGED":   (255, 80,  80),
            "REGROWING": GOLD,
            "RECOVERED": TEAL,
        }.get(self.phase_label, TEXT_DIM)

        self._panel(px, py, SIDEBAR_WIDTH - px*2, 44)
        self._txt(self.phase_label, self.font_title, phase_col, px + 10, py + 8)
        self._txt(f"t = {self.global_time:.1f}s", self.font_mono,
                  TEXT_DIM, SIDEBAR_WIDTH - px - 8, py + 14, align="right")
        py += 54

        # Cell counts
        self._panel(px, py, SIDEBAR_WIDTH - px*2, 70)
        alive = sum(1 for c in self.cells if c.state == ALIVE)
        dead  = sum(1 for c in self.cells if c.state == DEAD)
        grow  = sum(1 for c in self.cells if c.state == GROWING)
        total = len(self.cells)

        self._metric("Alive cells", f"{alive} / {total}", py + 10, TEAL)
        self._metric("Dead cells",  str(dead),             py + 30, (200, 60, 60) if dead > 0 else TEXT_DIM)
        self._metric("Regrowing",   str(grow),             py + 50, GOLD if grow > 0 else TEXT_DIM)
        py += 80

        # Series constants
        self._txt("SERIES CONSTANTS", self.font_small, TEAL, px, py)
        py += 14
        self._panel(px, py, SIDEBAR_WIDTH - px*2, 90)
        sp = py + 8

        self._txt("Bhaya — Crisis Fraction", self.font_small, TEXT_DIM, px+10, sp)
        bhaya_col = (255, 80, 80) if self.bhaya > BHAYA_QUIESCENCE_EXPECTED * 3 else TEAL
        self._txt(f"{self.bhaya:.5f}", self.font_mono, bhaya_col,
                  SIDEBAR_WIDTH - px - 8, sp, align="right")
        sp += 15
        self._txt(f"भय · Law: {BHAYA_QUIESCENCE_EXPECTED:.4f} expected",
                  self.font_small, (0, 140, 110), px+10, sp)
        sp += 18
        self._bar(px+10, sp, SIDEBAR_WIDTH - px*2 - 20, 5,
                  min(self.bhaya / 0.05, 1.0), (255, 80, 80))
        sp += 16

        pygame.draw.line(self.screen, BORDER_COLOR,
                         (px+8, sp), (SIDEBAR_WIDTH-px-8, sp))
        sp += 8

        self._txt("Vairagya Decay", self.font_small, TEXT_DIM, px+10, sp)
        self._txt(f"{VAIRAGYA_DECAY_RATE:.6f}", self.font_mono, WHITE,
                  SIDEBAR_WIDTH - px - 8, sp, align="right")
        sp += 15
        self._txt("वैराग्य · ORCID magic number", self.font_small,
                  (0, 140, 110), px+10, sp)
        py += 100

        # FRR
        self._txt("FUNCTIONAL RECOVERY RATE", self.font_small, TEAL, px, py)
        py += 14
        self._panel(px, py, SIDEBAR_WIDTH - px*2, 58)
        fp = py + 8

        if self.frr is not None:
            frr_pct = self.frr * 100
            frr_col = TEAL if frr_pct > 20 else GOLD if frr_pct > 0 else (200, 60, 60)
            self._txt(f"{frr_pct:.1f}%", self.font_large, frr_col, px+10, fp)
            self._bar(px+10, fp+26, SIDEBAR_WIDTH - px*2 - 20, 6, self.frr, frr_col)
            self._txt("Fixed baseline = 0.0%", self.font_small, TEXT_DIM,
                      px+10, fp + 36)
        elif self.phase_label == "RECOVERED":
            self._txt("100% — Fully recovered!", self.font_body, TEAL, px+10, fp)
        else:
            self._txt("—  Press T to cut tail", self.font_body, TEXT_DIM, px+10, fp)
        py += 68

        # Controls
        self._panel(px, py, SIDEBAR_WIDTH - px*2, 72)
        cp = py + 8
        controls = [
            ("T", "Cut the tail"),
            ("R", "Reset everything"),
            ("+/-", f"Pulse speed ({self.pulse_speed:.1f}x)"),
            ("Q", "Quit"),
        ]
        for key, desc in controls:
            self._txt(key,  self.font_mono,  GOLD,     px+10, cp)
            self._txt(desc, self.font_small, TEXT_DIM, px+50, cp)
            cp += 16
        py += 82

        # Log
        log_h = WINDOW_HEIGHT - py - 10
        if log_h > 30:
            self._panel(px, py, SIDEBAR_WIDTH - px*2, log_h)
            lp = py + 6
            per_line = 13
            visible  = max(1, (log_h - 12) // per_line)
            for line in self.log[-visible:]:
                if lp + per_line > py + log_h:
                    break
                col = TEAL          if "[init]"   in line else \
                      (255, 80, 80) if "[CUT]"    in line else \
                      GOLD          if "[REGROW]" in line else \
                      TEAL          if "[DONE]"   in line else \
                      TEXT_DIM
                display = line[:42] + "…" if len(line) > 43 else line
                self._txt(display, self.font_small, col, px+8, lp)
                lp += per_line

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _txt(self, text, font, colour, x, y, align="left"):
        s = font.render(str(text), True, colour)
        r = s.get_rect()
        if align == "left":   r.topleft  = (x, y)
        elif align == "right":r.topright = (x, y)
        elif align == "center":r.midtop  = (x, y)
        self.screen.blit(s, r)

    def _panel(self, x, y, w, h, radius=8):
        pygame.draw.rect(self.screen, (26, 26, 46),
                         pygame.Rect(x, y, w, h), border_radius=radius)
        pygame.draw.rect(self.screen, BORDER_COLOR,
                         pygame.Rect(x, y, w, h), 1, border_radius=radius)

    def _bar(self, x, y, w, h, value, colour, radius=3):
        pygame.draw.rect(self.screen, BORDER_COLOR,
                         pygame.Rect(x, y, w, h), border_radius=radius)
        fw = int(w * max(0.0, min(1.0, value)))
        if fw > 0:
            pygame.draw.rect(self.screen, colour,
                             pygame.Rect(x, y, fw, h), border_radius=radius)

    def _metric(self, label, value, y, vcol):
        self._txt(label, self.font_small, TEXT_DIM, 26, y)
        self._txt(value, self.font_mono,  vcol,
                  SIDEBAR_WIDTH - 26, y, align="right")

    def _add_log(self, msg):
        self.log.append(msg)
        if len(self.log) > 200:
            self.log = self.log[-200:]

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        print(f"\n[Maya-Morphe] Starting lizard visualizer")
        print(f"[Maya-Morphe] {len(self.cells)} cells packed into lizard shape")
        print(f"[Maya-Morphe] {CANARY}\n")

        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            dt = min(dt, 0.05)   # cap dt to prevent spiral of death on lag

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    k = event.key
                    if k in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif k == pygame.K_t:
                        self._trigger_amputation()
                    elif k == pygame.K_r:
                        self._reset()
                    elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self.pulse_speed = min(3.0, self.pulse_speed + 0.2)
                    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.pulse_speed = max(0.2, self.pulse_speed - 0.2)

            self.update(dt)
            self.draw()

        pygame.quit()
        print(f"\n[done] Session ended at t={self.global_time:.1f}s")
        print(f"[done] Bhaya final: {self.bhaya:.6f}")
        print(f"[done] {CANARY}")

    def _reset(self):
        self.cells                = []
        self.particles            = []
        self.amputation_active    = False
        self.regrowth_active      = False
        self.cut_y                = None
        self.phase_label          = "INTACT"
        self.frr                  = None
        self.bhaya                = 0.0
        self.global_time          = 0.0
        self._build_lizard()
        self._add_log("[reset] Lizard reset. Ready.")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = LizardVisualizer()
    app.run()
