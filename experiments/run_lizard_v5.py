"""
run_lizard_v5.py
================
Maya-Morphe Paper 1 — Cellular Lizard Visualizer v5
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

THREE MODES — press M to cycle:

  MODE 1 — SCRIPTED
    Timer-based. Control condition / baseline.
    FRR curve: smooth, predictable, deterministic.

  MODE 2 — VOLTAGE-DRIVEN
    Spatial field, radius=48px. Covers entire wound at once.
    Shows the voltage mechanism works. Not genuine propagation.
    FRR curve: fast jump — field is everywhere immediately.

  MODE 3 — VOLTAGE-PROPAGATING  ← the research claim
    Spatial field, radius=15px (one cell diameter).
    Gradient propagates hop by hop from stump to tail tip.
    Each newly growing cell becomes the next emitter.
    This is how bioelectric regeneration actually works.
    FRR curve: wave front — slow start, visible propagation.

The difference between Mode 2 and Mode 3 FRR curves is the
research finding. Mode 3 is what fills the gap in the literature.

Controls:
  T           Cut the tail
  M           Cycle mode (1 → 2 → 3 → 1)
  R           Reset
  +/-         Pulse speed
  Q / ESC     Quit

Run from Maya-Morphe-P1 root:
    python experiments/run_lizard_v5.py
"""

import sys
import os
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify_provenance
verify_provenance.stamp()

# ── Dependency checks ─────────────────────────────────────────────────────────
try:
    import pygame
except ImportError:
    print("[ERROR] pip install pygame")
    sys.exit(1)

try:
    from scipy.stats.qmc import PoissonDisk
except ImportError:
    print("[ERROR] pip install scipy")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("[ERROR] pip install pillow")
    sys.exit(1)

import numpy as np
from src.morphe.constants import CANARY, VAIRAGYA_DECAY_RATE, BHAYA_QUIESCENCE_EXPECTED
from src.morphe.voltage import (
    compute_spatial_voltage_field,
    compute_propagating_voltage_field,
    get_regrowth_threshold,
    get_wound_decay_rate,
    get_sense_radius,
)

# ── Mode constants ────────────────────────────────────────────────────────────
MODE_SCRIPTED     = "SCRIPTED"
MODE_VOLTAGE      = "VOLTAGE-DRIVEN"
MODE_PROPAGATING  = "VOLTAGE-PROPAGATING"
MODES             = [MODE_SCRIPTED, MODE_VOLTAGE, MODE_PROPAGATING]

MODE_COLOURS = {
    MODE_SCRIPTED:    (100, 180, 160),
    MODE_VOLTAGE:     (255, 215,   0),
    MODE_PROPAGATING: (0,   212, 170),
}

MODE_DESC = {
    MODE_SCRIPTED:    "Timer based — control condition",
    MODE_VOLTAGE:     "Field covers wound instantly",
    MODE_PROPAGATING: "Hop-by-hop propagation ← RESEARCH",
}

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 780
SIDEBAR_WIDTH = 300

CELL_RADIUS   = 14        # Poisson minimum distance — controls cell density
CELL_DRAW_R   = 9         # Visual radius of each cell (slightly smaller than grid)
GLOW_RADIUS   = 22        # Pre-cached glow surface radius

# Silhouette PNG path (generated on first run if missing)
ASSET_DIR     = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
PNG_PATH      = os.path.join(ASSET_DIR, "lizard_silhouette.png")

# Palette
BG            = (10,  10,  15)
SIDEBAR_BG    = (18,  18,  26)
BORDER_COL    = (42,  42,  62)
TEAL          = (0,   212, 170)
GOLD          = (255, 215, 0)
RED_DARK      = (40,  0,   0)
RED_HOT       = (200, 30,  30)
WHITE         = (255, 255, 255)
TEXT          = (200, 220, 220)
TEXT_DIM      = (100, 110, 130)

# Cell states
ALIVE   = 0
DYING   = 1
DEAD    = 2
GROWING = 3

# ─────────────────────────────────────────────────────────────────────────────
# SILHOUETTE GENERATOR  (runs once if PNG missing)
# ─────────────────────────────────────────────────────────────────────────────

def generate_silhouette(path: str):
    """Draw a top-down lizard silhouette and save as PNG."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    W, H = 900, 900
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    F    = (255, 255, 255, 255)
    cx, cy = 450, 480
    sc   = 1.6   # scale factor

    def p(dx, dy):
        return (int(cx + dx * sc), int(cy + dy * sc))

    def e(dx1, dy1, dx2, dy2):
        return [cx + dx1*sc, cy + dy1*sc, cx + dx2*sc, cy + dy2*sc]

    # HEAD — tapered pentagon
    draw.polygon([p(-55,-170), p(55,-170), p(38,-265), p(0,-300), p(-38,-265)], fill=F)
    # NECK
    draw.ellipse(e(-42,-195, 42,-155), fill=F)
    # TORSO
    draw.ellipse(e(-70,-165, 70, 95), fill=F)
    # EYE nubs
    draw.ellipse(e(-32,-238, -14,-222), fill=F)
    draw.ellipse(e( 14,-238,  32,-222), fill=F)
    # FRONT LEGS
    draw.polygon([p(-52,-110),p(-52,-75),p(-95,-55),p(-155,-68),p(-152,-92),p(-98,-82)], fill=F)
    draw.polygon([p( 52,-110),p( 52,-75),p( 95,-55),p( 155,-68),p( 152,-92),p( 98,-82)], fill=F)
    # BACK LEGS
    draw.polygon([p(-58,30),p(-58,75),p(-105,105),p(-168,85),p(-162,58),p(-105,72)], fill=F)
    draw.polygon([p( 58,30),p( 58,75),p( 105,105),p( 168,85),p( 162,58),p( 105,72)], fill=F)
    # BODY-TAIL JUNCTION
    draw.ellipse(e(-58,60, 58,115), fill=F)
    # TAIL — overlapping ellipses for smooth organic taper
    for i in range(42):
        t  = i / 41
        tx = cx + math.sin(t * math.pi * 0.7) * 55 * sc
        ty = cy + 88*sc + t * 255*sc
        w  = max(3, int(52 * sc * (1 - t) ** 0.75))
        draw.ellipse([tx-w, ty-w, tx+w, ty+w], fill=F)

    img.save(path)
    print(f"[asset] Lizard silhouette generated: {path}")
    return path

# ─────────────────────────────────────────────────────────────────────────────
# PARTICLE
# ─────────────────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y):
        self.x    = float(x)
        self.y    = float(y)
        angle     = random.uniform(0, math.pi * 2)
        speed     = random.uniform(100, 380)
        self.vx   = math.cos(angle) * speed
        self.vy   = math.sin(angle) * speed
        self.life = 1.0
        self.size = random.randint(2, 4)
        self.col  = random.choice([(0,255,180),(255,215,0),(255,255,200)])

    def update(self, dt):
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.vx   *= 0.90
        self.vy   *= 0.90
        self.life -= dt * 2.0
        return self.life > 0

# ─────────────────────────────────────────────────────────────────────────────
# CELL
# ─────────────────────────────────────────────────────────────────────────────

class Cell:
    __slots__ = [
        "x", "y", "region",
        "state", "base_voltage", "current_voltage",
        "delay_timer", "decay_timer"
    ]

    def __init__(self, x, y, region):
        self.x             = float(x)
        self.y             = float(y)
        self.region        = region
        self.state         = ALIVE
        self.base_voltage  = random.uniform(0.30, 0.60)
        self.current_voltage = self.base_voltage
        self.delay_timer   = 0.0
        self.decay_timer   = 0.0

    def color(self):
        if self.state == DEAD:
            return RED_DARK
        if self.state == GROWING:
            # New tissue — pale yellow-green, brightens as it matures
            t = min(self.current_voltage / max(self.base_voltage, 0.01), 1.0)
            r = int(80  + t * (0   - 80))
            g = int(180 + t * (212 - 180))
            b = int(40  + t * (100 - 40))
            return (max(0,r), max(0,g), max(0,b))
        v  = max(0.0, min(1.0, self.current_voltage))
        # dark green → teal → white
        if v < 0.5:
            t = v * 2.0
            return (
                int(10  + (0   - 10 ) * t),
                int(55  + (212 - 55 ) * t),
                int(20  + (170 - 20 ) * t),
            )
        else:
            t = (v - 0.5) * 2.0
            return (
                int(0   + 255 * t),
                int(212 + (255 - 212) * t),
                int(170 + (255 - 170) * t),
            )

# ─────────────────────────────────────────────────────────────────────────────
# MAIN VISUALIZER
# ─────────────────────────────────────────────────────────────────────────────

class LizardV3:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(
            "Maya-Morphe v5 — 3-Mode Cellular Lizard | Nexus Learning Labs | ORCID: 0000-0002-3315-7907"
        )
        self.clock = pygame.time.Clock()

        # Fonts
        self.f_large  = self._font(22, bold=True)
        self.f_title  = self._font(16, bold=True)
        self.f_body   = self._font(14)
        self.f_small  = self._font(12)
        self.f_mono   = self._mono(12)
        self.f_huge   = self._font(34, bold=True)

        # Pre-cache glow surface (drawn once)
        self.glow_surf = self._make_glow(GLOW_RADIUS)

        # Viewport centre for the lizard
        self.vp_cx = SIDEBAR_WIDTH + (WINDOW_WIDTH - SIDEBAR_WIDTH) // 2
        self.vp_cy = WINDOW_HEIGHT // 2

        # Generate PNG if missing
        if not os.path.exists(PNG_PATH):
            generate_silhouette(PNG_PATH)

        # Load silhouette + build mask
        print("[v3] Loading silhouette and building mask...")
        self._load_mask()

        # Pack cells with Poisson disk sampling
        print("[v3] Packing cells via Poisson disk sampling...")
        self._pack_cells()

        # Animation state
        self.global_time       = 0.0
        self.amputation_active = False
        self.regrowth_active   = False
        self.cut_y             = None
        self.phase             = "INTACT"
        self.frr               = None
        self.bhaya             = 0.0
        self.particles         = []
        self.pulse_speed       = 1.0

        # Mode — M key cycles 1→2→3→1
        self.mode              = MODE_SCRIPTED
        self.voltage_field     = {}

        # ── Screenshot system ──────────────────────────────────────────────────
        # Auto-captures at 4 key paper moments + manual S key
        self.figures_dir       = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures"
        )
        os.makedirs(self.figures_dir, exist_ok=True)

        self._fig_captured     = {
            "fig1_intact":       False,
            "fig2_damaged":      False,
            "fig3_regrowing":    False,
            "fig4_recovered":    False,
        }
        self._fig1_delay       = 3.0   # capture Fig1 after 3s (lizard fully rendered)
        self._frr_peak_for_fig3 = 0.35  # capture Fig3 when FRR first crosses 35%

        self.log = [
            f"[init] {CANARY}",
            f"[init] {len(self.cells)} cells packed via Poisson disk",
            f"[init] Silhouette mask: {self.mask_w}×{self.mask_h}px",
            f"[init] Mode 1=SCRIPTED  2=VOLTAGE  3=PROPAGATING",
            "[ctrl] T=cut  M=cycle mode  R=reset  Q=quit",
        ]

        print(f"[v3] Ready — {len(self.cells)} cells")

    # ── Font helpers ──────────────────────────────────────────────────────────

    def _font(self, size, bold=False):
        for name in ["Segoe UI", "Arial", "Helvetica", ""]:
            try:    return pygame.font.SysFont(name, size, bold=bold)
            except: pass
        return pygame.font.Font(None, size)

    def _mono(self, size):
        for name in ["Consolas", "Courier New", "Lucida Console", ""]:
            try:    return pygame.font.SysFont(name, size)
            except: pass
        return pygame.font.Font(None, size)

    # ── Glow surface ──────────────────────────────────────────────────────────

    def _make_glow(self, radius):
        surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(160 * (1 - (r/radius)**2))
            pygame.draw.circle(surf, (0, 190, 150, a), (radius, radius), r)
        return surf

    # ── Silhouette mask ───────────────────────────────────────────────────────

    def _load_mask(self):
        """Load PNG → scale to fit viewport → build pygame.mask."""
        raw  = pygame.image.load(PNG_PATH).convert_alpha()
        rw, rh = raw.get_size()

        # Scale so lizard fits in viewport with padding
        avail_w = WINDOW_WIDTH  - SIDEBAR_WIDTH - 60
        avail_h = WINDOW_HEIGHT - 60
        scale   = min(avail_w / rw, avail_h / rh)
        nw      = int(rw * scale)
        nh      = int(rh * scale)

        self.lizard_surf = pygame.transform.smoothscale(raw, (nw, nh))
        self.mask        = pygame.mask.from_surface(self.lizard_surf)
        self.mask_w      = nw
        self.mask_h      = nh

        # Top-left offset so lizard is centred in viewport
        self.mask_ox = SIDEBAR_WIDTH + (WINDOW_WIDTH - SIDEBAR_WIDTH - nw) // 2
        self.mask_oy = (WINDOW_HEIGHT - nh) // 2

        # Region boundaries in mask-local coordinates
        self.region_head_y  = int(nh * 0.22)
        self.region_body_y  = int(nh * 0.72)
        self.region_body_x0 = int(nw * 0.30)
        self.region_body_x1 = int(nw * 0.70)

    # ── Poisson disk cell packing ─────────────────────────────────────────────

    def _pack_cells(self):
        """Pack cells inside the mask using Bridson's Poisson disk algorithm."""
        W, H = self.mask_w, self.mask_h
        r    = CELL_RADIUS / max(W, H)

        engine   = PoissonDisk(d=2, radius=r, seed=42)
        pts_norm = engine.fill_space()

        self.cells = []
        for px, py in pts_norm:
            mx = int(px * W)
            my = int(py * H)
            if mx < 0 or mx >= W or my < 0 or my >= H:
                continue
            if not self.mask.get_at((mx, my)):
                continue
            # Convert mask-local → screen coordinates
            sx = self.mask_ox + mx
            sy = self.mask_oy + my
            region = self._classify(mx, my)
            self.cells.append(Cell(sx, sy, region))

        self._original_tail = sum(1 for c in self.cells if c.region == "TAIL")

    def _classify(self, mx, my):
        """Region label from mask-local coordinates."""
        W, H = self.mask_w, self.mask_h
        if my < self.region_head_y:
            return "HEAD"
        elif my > self.region_body_y:
            return "TAIL"
        elif mx < self.region_body_x0:
            return "FRONT_LEG_L" if my < H * 0.50 else "BACK_LEG_L"
        elif mx > self.region_body_x1:
            return "FRONT_LEG_R" if my < H * 0.50 else "BACK_LEG_R"
        else:
            return "BODY"

    # ── Amputation ────────────────────────────────────────────────────────────

    def _cut(self):
        if self.amputation_active:
            self._log("[ctrl] Already cut — press R to reset")
            return

        tail = [c for c in self.cells if c.region == "TAIL"]
        if not tail:
            return

        self.amputation_active = True
        self.phase = "DAMAGED"

        y_min = min(c.y for c in tail)
        y_max = max(c.y for c in tail)
        self.cut_y = y_min + (y_max - y_min) * 0.35

        # Kill ALL tail cells below cut_y — region check ensures
        # no tail cell survives regardless of Poisson position scatter
        severed = sorted(
            [c for c in self.cells
             if c.region == "TAIL" and c.y > self.cut_y],
            key=lambda c: c.y, reverse=True
        )
        for idx, cell in enumerate(severed):
            # +0.01 ensures delay_timer > 0 for ALL cells including idx=0
            # Without this, tip cells get delay=0.0 and never trigger death
            cell.delay_timer = 0.01 + (idx / max(len(severed), 1)) * 1.2

        # Wound flare + permanent base elevation for stump cells
        # base_voltage raised so ambient pulse keeps stump hot throughout
        for c in tail:
            if c.y <= self.cut_y:
                c.base_voltage = 0.78   # elevated wound potential
                c.current_voltage = 1.0  # initial flare

        # Particles
        stump = [c for c in tail if c.y <= self.cut_y]
        if stump:
            bx = sum(c.x for c in stump) / len(stump)
            for _ in range(50):
                self.particles.append(Particle(bx, self.cut_y))

        self._log(f"[CUT] {len(severed)} cells severed — watching FRR...")

    def _regrow(self):
        if self.regrowth_active:
            return
        self.regrowth_active = True
        self.phase = "REGROWING"

        dead = sorted(
            [c for c in self.cells if c.region == "TAIL" and c.state == DEAD],
            key=lambda c: c.y
        )

        if self.mode == MODE_SCRIPTED:
            for idx, cell in enumerate(dead):
                cell.delay_timer = (idx / max(len(dead), 1)) * 6.0
            self._log(f"[MODE 1] {len(dead)} cells on timer from stump...")

        elif self.mode == MODE_VOLTAGE:
            for cell in dead:
                cell.delay_timer = 0.0
            self._log(f"[MODE 2] {len(dead)} cells waiting for field...")
            self._log(f"[MODE 2] radius=48px  threshold={get_regrowth_threshold():.3f}")

        else:  # MODE_PROPAGATING
            for cell in dead:
                cell.delay_timer = 0.0
            self._log(f"[MODE 3] {len(dead)} cells waiting for wavefront...")
            self._log(f"[MODE 3] radius=15px  threshold={get_regrowth_threshold(3):.3f}")

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self.global_time += dt
        self.particles = [p for p in self.particles if p.update(dt)]

        alive_tail  = 0
        dead_count  = 0
        dying_count = 0
        grow_count  = 0

        # ── Compute voltage field for Mode 2 and Mode 3 ──────────────────────
        if self.regrowth_active:
            if self.mode == MODE_VOLTAGE:
                self.voltage_field = compute_spatial_voltage_field(self.cells)
            elif self.mode == MODE_PROPAGATING:
                self.voltage_field = compute_propagating_voltage_field(self.cells)
            else:
                self.voltage_field = {}
        else:
            self.voltage_field = {}

        threshold    = get_regrowth_threshold(3 if self.mode == MODE_PROPAGATING else 2)
        wound_decay  = get_wound_decay_rate()

        for cell in self.cells:

            if cell.state == ALIVE:
                if cell.region == "TAIL":
                    alive_tail += 1

                # Ambient voltage pulse
                pulse = math.sin(
                    self.global_time * 1.8 * self.pulse_speed
                    + cell.y * 0.04 + cell.x * 0.02
                ) * 0.12
                cell.current_voltage = cell.base_voltage + pulse

                # Wound voltage gradually decays back to resting
                if (self.regrowth_active
                        and cell.region == "TAIL"
                        and cell.current_voltage > cell.base_voltage + 0.1):
                    cell.current_voltage -= wound_decay * dt

                # Count down to death (amputation)
                if (self.amputation_active
                        and cell.region == "TAIL"
                        and self.cut_y is not None
                        and cell.y > self.cut_y
                        and cell.delay_timer > 0):
                    cell.delay_timer -= dt
                    if cell.delay_timer <= 0:
                        cell.state       = DYING
                        cell.decay_timer = 0.20

            elif cell.state == DYING:
                dying_count += 1
                cell.current_voltage -= dt / 0.20
                cell.decay_timer     -= dt
                if cell.decay_timer <= 0:
                    cell.state           = DEAD
                    cell.current_voltage = 0.0

            elif cell.state == DEAD:
                dead_count += 1

                if self.regrowth_active:
                    if self.mode == MODE_SCRIPTED:
                        # MODE 1: timer-driven
                        if cell.delay_timer > 0:
                            cell.delay_timer -= dt
                            if cell.delay_timer <= 0:
                                cell.state           = GROWING
                                cell.current_voltage = 0.05
                    else:
                        # MODE 2 and MODE 3: voltage field driven
                        field_v = self.voltage_field.get(id(cell), 0.0)
                        # Show field strength on dead cells visually
                        cell.current_voltage = field_v * 0.4
                        mode_num = 3 if self.mode == MODE_PROPAGATING else 2
                        if field_v >= get_regrowth_threshold(mode_num):
                            cell.state           = GROWING
                            cell.current_voltage = 0.05

            elif cell.state == GROWING:
                grow_count += 1
                cell.current_voltage = min(
                    cell.base_voltage,
                    cell.current_voltage + dt * 0.15
                )
                if cell.current_voltage >= cell.base_voltage * 0.95:
                    cell.state = ALIVE

        # FRR = recovered severed cells / total severed cells
        # Stump cells (above cut_y) are never counted — they never died
        # This gives true recovery rate of the damaged tissue only
        if self.amputation_active and self.cut_y is not None:
            severed_alive = sum(
                1 for c in self.cells
                if c.region == "TAIL"
                and c.y > self.cut_y
                and c.state == ALIVE
            )
            severed_total = sum(
                1 for c in self.cells
                if c.region == "TAIL"
                and c.y > self.cut_y
            )
            self.frr = severed_alive / max(severed_total, 1)
        else:
            self.frr = None

        # Bhaya
        alive_total = sum(1 for c in self.cells if c.state == ALIVE)
        crisis = sum(1 for c in self.cells
                     if c.state == ALIVE and c.current_voltage > 0.85)
        self.bhaya = crisis / max(alive_total, 1)

        # Auto-trigger regrowth
        if (self.amputation_active
                and not self.regrowth_active
                and dying_count == 0
                and dead_count > 0):
            self._regrow()

        # Recovery complete — all severed cells recovered
        if (self.regrowth_active
                and grow_count == 0
                and dead_count == 0):
            self.amputation_active = False
            self.regrowth_active   = False
            self.cut_y             = None
            self.phase             = "RECOVERED"
            self.frr               = None
            self.voltage_field     = {}
            self._log("[DONE] Tail fully regenerated! FRR = 100%")

    # ── Render ────────────────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(BG)

        # ── Cells — base pass ─────────────────────────────────────────────────
        glow_queue = []
        for cell in self.cells:
            cx = int(cell.x) - CELL_DRAW_R
            cy_pos = int(cell.y) - CELL_DRAW_R
            rect = pygame.Rect(cx, cy_pos, CELL_DRAW_R*2, CELL_DRAW_R*2)

            if cell.state == DEAD:
                pygame.draw.rect(self.screen, RED_DARK, rect, border_radius=4)
                pygame.draw.rect(self.screen, RED_HOT,  rect, 1, border_radius=4)
            else:
                col = cell.color()
                pygame.draw.rect(self.screen, col, rect, border_radius=4)
                # Alive at high voltage OR growing (new tissue) both glow
                if cell.current_voltage > 0.68 or cell.state == GROWING:
                    glow_queue.append((int(cell.x), int(cell.y)))

        # ── Additive glow pass ────────────────────────────────────────────────
        gr = GLOW_RADIUS
        for gx, gy in glow_queue:
            self.screen.blit(
                self.glow_surf,
                (gx - gr, gy - gr),
                special_flags=pygame.BLEND_RGB_ADD
            )

        # ── Cut line ─────────────────────────────────────────────────────────
        if self.cut_y is not None:
            pygame.draw.line(
                self.screen, (180, 40, 40),
                (SIDEBAR_WIDTH, int(self.cut_y)),
                (WINDOW_WIDTH,  int(self.cut_y)), 1
            )

        # ── Particles ─────────────────────────────────────────────────────────
        for p in self.particles:
            col = tuple(min(255, int(c * p.life)) for c in p.col)
            pygame.draw.circle(
                self.screen, col,
                (int(p.x), int(p.y)), p.size
            )

        # ── Sidebar ───────────────────────────────────────────────────────────
        self._draw_sidebar()
        pygame.display.flip()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _draw_sidebar(self):
        pygame.draw.rect(self.screen, SIDEBAR_BG,
                         pygame.Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(self.screen, GOLD,
                         (SIDEBAR_WIDTH, 0), (SIDEBAR_WIDTH, WINDOW_HEIGHT), 2)

        px, py = 16, 14

        self._t("Maya-Morphe", self.f_large, TEAL, px, py)
        py += 26
        self._t("Morphogenetic Computing", self.f_small, TEXT_DIM, px, py)
        py += 15
        self._t("Nexus Learning Labs · Series 3", self.f_small, TEXT_DIM, px, py)
        py += 18
        pygame.draw.line(self.screen, BORDER_COL, (px,py),(SIDEBAR_WIDTH-px,py))
        py += 12

        # Phase
        pcol = {
            "INTACT":    TEAL,
            "DAMAGED":   (255, 80, 80),
            "REGROWING": GOLD,
            "RECOVERED": TEAL,
        }.get(self.phase, TEXT_DIM)
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 44)
        self._t(self.phase, self.f_title, pcol, px+10, py+8)
        self._t(f"t={self.global_time:.1f}s", self.f_mono, TEXT_DIM,
                SIDEBAR_WIDTH-px-8, py+14, "right")
        py += 54

        # Mode badge
        mode_col = MODE_COLOURS.get(self.mode, TEXT_DIM)
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 34)
        self._t(f"MODE: {self.mode}", self.f_small, mode_col, px+10, py+5)
        self._t("M to cycle", self.f_small, TEXT_DIM,
                SIDEBAR_WIDTH-px-8, py+5, "right")
        self._t(MODE_DESC.get(self.mode, ""),
                self.f_small, (0, 140, 110) if self.mode == MODE_PROPAGATING
                else (80, 100, 80), px+10, py+18)
        py += 44

        # Cell counts
        alive = sum(1 for c in self.cells if c.state == ALIVE)
        dead  = sum(1 for c in self.cells if c.state == DEAD)
        grow  = sum(1 for c in self.cells if c.state == GROWING)
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 72)
        self._row("Alive cells", f"{alive}/{len(self.cells)}", py+10, TEAL)
        self._row("Dead cells",  str(dead),  py+30, (200,60,60) if dead else TEXT_DIM)
        self._row("Regrowing",   str(grow),  py+50, GOLD if grow else TEXT_DIM)
        py += 82

        # Series constants
        self._t("SERIES CONSTANTS", self.f_small, TEAL, px, py)
        py += 14
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 90)
        sp = py + 8

        self._t("Bhaya — Crisis Fraction", self.f_small, TEXT_DIM, px+10, sp)
        bcol = (255,80,80) if self.bhaya > BHAYA_QUIESCENCE_EXPECTED*3 else TEAL
        self._t(f"{self.bhaya:.5f}", self.f_mono, bcol, SIDEBAR_WIDTH-px-8, sp, "right")
        sp += 15
        self._t(f"भय · Law: {BHAYA_QUIESCENCE_EXPECTED:.4f}", self.f_small,
                (0,140,110), px+10, sp)
        sp += 14
        self._bar(px+10, sp, SIDEBAR_WIDTH-px*2-20, 5,
                  min(self.bhaya/0.05, 1.0), (255,80,80))
        sp += 14
        pygame.draw.line(self.screen, BORDER_COL,
                         (px+8,sp),(SIDEBAR_WIDTH-px-8,sp))
        sp += 8
        self._t("Vairagya Decay", self.f_small, TEXT_DIM, px+10, sp)
        self._t(f"{VAIRAGYA_DECAY_RATE:.6f}", self.f_mono, WHITE,
                SIDEBAR_WIDTH-px-8, sp, "right")
        sp += 14
        self._t("वैराग्य · ORCID magic", self.f_small, (0,140,110), px+10, sp)
        py += 100

        # FRR
        self._t("FUNCTIONAL RECOVERY RATE", self.f_small, TEAL, px, py)
        py += 14
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 58)
        fp = py + 8
        if self.frr is not None:
            fc = TEAL if self.frr>0.2 else GOLD if self.frr>0 else (200,60,60)
            self._t(f"{self.frr*100:.1f}%", self.f_large, fc, px+10, fp)
            self._bar(px+10, fp+26, SIDEBAR_WIDTH-px*2-20, 6, self.frr, fc)
            self._t("Fixed baseline = 0.0%", self.f_small, TEXT_DIM, px+10, fp+38)
        elif self.phase == "RECOVERED":
            self._t("100% — Fully recovered!", self.f_body, TEAL, px+10, fp)
        else:
            self._t("— Press T to cut tail", self.f_body, TEXT_DIM, px+10, fp)
        py += 68

        # Controls
        self._panel(px, py, SIDEBAR_WIDTH-px*2, 92)
        cp = py + 8
        for key, desc in [("T","Cut the tail"),
                          ("M","Cycle mode (1→2→3→1)"),
                          ("S","Screenshot now"),
                          ("R","Reset"),
                          ("+/-",f"Pulse speed ({self.pulse_speed:.1f}x)"),
                          ("Q","Quit")]:
            self._t(key,  self.f_mono,  GOLD,     px+10, cp)
            self._t(desc, self.f_small, TEXT_DIM, px+50, cp)
            cp += 14
        py += 102

        # Log
        lh = WINDOW_HEIGHT - py - 10
        if lh > 30:
            self._panel(px, py, SIDEBAR_WIDTH-px*2, lh)
            lp = py + 6
            vis = max(1, (lh-12)//13)
            for line in self.log[-vis:]:
                if lp+13 > py+lh: break
                col = TEAL if "[init]" in line else \
                      (255,80,80) if "[CUT]" in line else \
                      GOLD if "[REGROW]" in line else \
                      TEAL if "[DONE]" in line else TEXT_DIM
                self._t(line[:42]+("…" if len(line)>43 else ""),
                        self.f_small, col, px+8, lp)
                lp += 13

    # ── Draw helpers ──────────────────────────────────────────────────────────

    def _t(self, text, font, col, x, y, align="left"):
        s = font.render(str(text), True, col)
        r = s.get_rect()
        if align=="left":    r.topleft  = (x,y)
        elif align=="right": r.topright = (x,y)
        elif align=="center":r.midtop   = (x,y)
        self.screen.blit(s, r)

    def _panel(self, x, y, w, h, rad=8):
        pygame.draw.rect(self.screen, (26,26,46), pygame.Rect(x,y,w,h), border_radius=rad)
        pygame.draw.rect(self.screen, BORDER_COL, pygame.Rect(x,y,w,h), 1, border_radius=rad)

    def _bar(self, x, y, w, h, v, col, rad=3):
        pygame.draw.rect(self.screen, BORDER_COL, pygame.Rect(x,y,w,h), border_radius=rad)
        fw = int(w * max(0.0, min(1.0, v)))
        if fw > 0:
            pygame.draw.rect(self.screen, col, pygame.Rect(x,y,fw,h), border_radius=rad)

    def _row(self, label, val, y, vcol):
        self._t(label, self.f_small, TEXT_DIM, 26, y)
        self._t(val,   self.f_mono,  vcol, SIDEBAR_WIDTH-26, y, "right")

    def _log(self, msg):
        self.log.append(msg)
        if len(self.log) > 200:
            self.log = self.log[-200:]

    def _toggle_mode(self):
        if self.amputation_active or self.regrowth_active:
            self._log("[ctrl] Reset first before switching mode")
            return
        idx = MODES.index(self.mode)
        self.mode = MODES[(idx + 1) % len(MODES)]
        self._log(f"[mode] → {self.mode}")
        self._log(f"[mode] {MODE_DESC[self.mode]}")

    # ── Screenshot system ─────────────────────────────────────────────────────

    def _save_screenshot(self, label: str, auto: bool = False):
        """Save current screen to figures/ directory."""
        import datetime
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{label}_{ts}.png"
        path  = os.path.join(self.figures_dir, fname)
        pygame.image.save(self.screen, path)
        prefix = "[AUTO]" if auto else "[SNAP]"
        self._log(f"{prefix} Saved: figures/{fname}")
        print(f"{prefix} Screenshot saved: {path}")
        return path

    def _check_auto_screenshots(self):
        """Auto-capture screenshots at the 4 key paper moments."""

        # Figure 1 — INTACT: capture after 3 seconds of stable run
        if (not self._fig_captured["fig1_intact"]
                and self.phase == "INTACT"
                and self.global_time >= self._fig1_delay):
            self._save_screenshot("fig1_intact", auto=True)
            self._fig_captured["fig1_intact"] = True

        # Figure 2 — POST-AMPUTATION: capture when phase changes to DAMAGED
        # and at least one dying cell exists (cut is fresh)
        if (not self._fig_captured["fig2_damaged"]
                and self.phase == "DAMAGED"
                and self._fig_captured["fig1_intact"]):
            dying = sum(1 for c in self.cells if c.state == DYING)
            if dying > 0:
                self._save_screenshot("fig2_post_amputation", auto=True)
                self._fig_captured["fig2_damaged"] = True

        # Figure 3 — REGROWING: capture when FRR first crosses 35%
        if (not self._fig_captured["fig3_regrowing"]
                and self.phase == "REGROWING"
                and self.frr is not None
                and self.frr >= self._frr_peak_for_fig3):
            self._save_screenshot("fig3_regrowing", auto=True)
            self._fig_captured["fig3_regrowing"] = True

        # Figure 4 — RECOVERED: capture when phase changes to RECOVERED
        if (not self._fig_captured["fig4_recovered"]
                and self.phase == "RECOVERED"):
            self._save_screenshot("fig4_recovered", auto=True)
            self._fig_captured["fig4_recovered"] = True

    def _reset(self):
        self.particles         = []
        self.amputation_active = False
        self.regrowth_active   = False
        self.cut_y             = None
        self.phase             = "INTACT"
        self.frr               = None
        self.bhaya             = 0.0
        self.global_time       = 0.0
        self.voltage_field     = {}
        # Reset fig2-4 so they re-capture on next run — keep fig1 (lizard unchanged)
        self._fig_captured["fig2_damaged"]    = False
        self._fig_captured["fig3_regrowing"]  = False
        self._fig_captured["fig4_recovered"]  = False
        self._pack_cells()
        self._log(f"[reset] Ready. Mode: {self.mode}")
    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    k = event.key
                    if k in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif k == pygame.K_t:
                        self._cut()
                    elif k == pygame.K_m:
                        self._toggle_mode()
                    elif k == pygame.K_r:
                        self._reset()
                    elif k == pygame.K_s:
                        # Manual screenshot — saves with current phase label
                        label = f"manual_{self.phase.lower()}"
                        self._save_screenshot(label, auto=False)
                    elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self.pulse_speed = min(3.0, self.pulse_speed + 0.2)
                    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.pulse_speed = max(0.2, self.pulse_speed - 0.2)

            self.update(dt)
            self.draw()
            self._check_auto_screenshots()  # auto-capture at key moments

        pygame.quit()
        print(f"\n[done] t={self.global_time:.1f}s | bhaya={self.bhaya:.6f}")
        print(f"[done] {CANARY}")


if __name__ == "__main__":
    app = LizardV3()
    app.run()
