# Maya-Morphe P1 — Bioelectric Gradient Fields as Computational Topology Primitives

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.XXXXXXX-blue)](https://doi.org/10.5281/zenodo.XXXXXXX)
[![Series](https://img.shields.io/badge/Series-Maya--Morphe%20%231-teal)](https://venky2099.github.io)
[![Status](https://img.shields.io/badge/Status-Published-green)](https://github.com/venky2099/Maya-Morphe-P1)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0002--3315--7907-brightgreen)](https://orcid.org/0000-0002-3315-7907)
[![Python](https://img.shields.io/badge/Python-3.11.9-blue)](https://python.org)
[![Hardware](https://img.shields.io/badge/Hardware-RTX%204060%208GB-orange)](https://github.com/venky2099/Maya-Morphe-P1)

**Venkatesh Swaminathan** · Nexus Learning Labs, Bengaluru
[Paper](https://doi.org/10.5281/zenodo.XXXXXXX) · [Dashboard](https://venky2099.github.io/Maya-Morphe-P1/dashboard.html) · [FAQ](https://venky2099.github.io/Maya-Morphe-P1/docs/faq.html) · [Hub](https://venky2099.github.io)

---

## What is this?

Maya-Morphe Paper 1 introduces **morphogenetic computing** — a new computational paradigm in which neural network topology self-organises via spatial bioelectric voltage gradient fields, inspired by Michael Levin's work on bioelectric tissue regeneration.

We ask: *can a network whose topology repairs itself via voltage gradient signals solve problems that fixed-topology networks fundamentally cannot?*

The answer is yes. A voltage-driven network achieves **99.7% Functional Recovery Rate (FRR)** after node removal. A fixed-topology network achieves **0.0% FRR** — it cannot self-repair by definition.

This paper formalises FRR as the first evaluation metric for morphogenetic topology repair, and establishes the experimental protocol for the Maya-Morphe series.

---

## Key Results

| Condition | FRR (mean) | Recovered | Bhaya Peak |
|---|---|---|---|
| **VOLTAGE_DRIVEN** | **99.7%** | **12/12** | 0.04858 |
| SCRIPTED | 99.5% | 12/12 | 0.04870 |
| FIXED_TOPOLOGY_BASELINE | 0.0% | 0/12 | 0.00000 |

Ablation: 3 conditions x 4 damage fractions [10%, 30%, 50%, 70%] x 3 seeds [42, 7, 2315] = 36 trials. Runtime: 6 seconds on CPU.

---

## Series Law Confirmation

| Series Constant | Expected | Observed | Status |
|---|---|---|---|
| Bhaya Quiescence Law | 0.0032 | ~0.0487 | MODIFIED |
| Vairagya = 0.002315 | ORCID magic | Embedded in all params | Confirmed |

The Bhaya Quiescence Law is reported honestly as MODIFIED. Wound response produces stronger crisis signal (~4.87%) than the SNN substrate (0.32%).

---

## Methodology Contribution

Three novel contributions:

**1. Functional Recovery Rate (FRR)** — first formal metric for morphogenetic topology repair.

**2. Voltage-Driven Spatial Repair** — dead nodes revive only when the spatial bioelectric field from surviving stump nodes exceeds a threshold. No timers. Emergent repair.

**3. Vairagya Decay as a Morphogenetic Primitive** — ORCID-derived constant 0.002315 governs gradient attenuation, embedding provenance into the physics of the model.

---

## Architecture

```
Maya-Morphe-P1/
├── src/morphe/
│   ├── constants.py          — canonical hyperparams, ORCID magic
│   ├── voltage.py            — spatial diffusion engine (Mode 2/3)
│   ├── grid.py               — NetworkX cell grid
│   ├── topology.py           — edge growth/pruning + FRR metric
│   └── prana.py              — energy budget engine
├── experiments/
│   ├── run_lizard_v5.py      — 3-mode PyGame cellular lizard visualizer
│   └── run_ablation.py       — headless ablation study (36 trials, 6s)
├── assets/
│   └── lizard_silhouette.png — PIL-generated silhouette mask
├── results/
│   ├── ablation_results.csv  — raw data, all 36 runs
│   ├── ablation_summary.txt  — paper-ready tables
│   └── bhaya_log.csv         — series constant analysis
├── docs/
│   └── faq.html              — trilingual FAQ
├── dashboard.html            — interactive dashboard + JS visualizer
├── verify_provenance.py      — IP protection (runs at startup)
├── CITATION.cff              — GitHub cite button
└── LICENSE                   — MIT + ORCID attribution
```

---

## Canonical Hyperparameters

| Parameter | Value | Notes |
|---|---|---|
| `VAIRAGYA_DECAY_RATE` | **0.002315** | ORCID magic number |
| `PRANA_COST_RATE` | **0.002315** | ORCID magic number |
| `SPATIAL_SENSE_RADIUS_M2` | 48.0 px | Mode 2: covers wound at once |
| `SPATIAL_SENSE_RADIUS_M3` | 15.0 px | Mode 3: hop-by-hop |
| `REGROWTH_VOLTAGE_THRESHOLD` | 0.18 | Mode 2 revival threshold |
| `REGROWTH_VOLTAGE_THRESHOLD_M3` | 0.06 | Mode 3 revival threshold |
| `GROWING_CELL_EMIT_VOLTAGE` | 0.95 | Propagation wave voltage |
| `STUMP_BASE_VOLTAGE` | 0.78 | Elevated wound potential |
| `BHAYA_QUIESCENCE_EXPECTED` | 0.0032 | Series law reference |
| `DAMAGE_FRACTIONS` | [0.1, 0.3, 0.5, 0.7] | Ablation sweep |
| `RANDOM_SEEDS` | [42, 7, 2315] | Reproducibility seeds |

---

## How to Run

```powershell
pip install pygame scipy pillow numpy networkx

# 3-mode cellular lizard visualizer
python experiments/run_lizard_v5.py
# T=cut tail  M=cycle mode  R=reset  Q=quit

# Full ablation study (36 trials, ~6 seconds)
python experiments/run_ablation.py
```

Expected ablation output:
```
VOLTAGE_DRIVEN:  FRR 99.7% | 12/12 recovered
SCRIPTED:        FRR 99.5% | 12/12 recovered
FIXED_TOPOLOGY:  FRR  0.0% |  0/12 recovered
All runs complete in 6.0s
```

---

## IP Protection Stack

| Layer | Status |
|---|---|
| MIT License + ORCID attribution | LICENSE |
| Runtime verification | verify_provenance.py |
| Run script canary | import verify_provenance in all run scripts |
| GitHub cite button | CITATION.cff |
| Document watermark | White-text ORCID + DOI in Word export |
| Figure steganography | LSB signature via sign_paper.py |
| Canary string | MayaNexusVS2026NLL_Bengaluru_Narasimha |
| Website legal | terms.html on venky2099.github.io |

---

## Limitations

- Small scale: 339 cells, ~63 tail cells. Larger grids are Paper 2 scope.
- Mode 3 (hop-by-hop propagation) deferred to Paper 2 on Vertex AI H100.
- Bhaya Quiescence Law MODIFIED — reported honestly.
- FRR recovery declared at >=98% to account for discretisation artifacts.
- Computational model only — no biological validation.

---

## Full Maya Series

| Paper | Title | DOI | Status |
|---|---|---|---|
| Maya-1 to Maya-9 | SNN Antahkarana Series | Various | Published |
| Maya-D1 to Maya-D4 | Defence Series | Various | Published |
| **Morphe-1** | **Maya-Morphe P1** | **10.5281/zenodo.XXXXXXX** | **This paper** |

---

## BibTeX

```bibtex
@software{swaminathan2026mayamorphe,
  author    = {Swaminathan, Venkatesh},
  title     = {{Maya-Morphe: Bioelectric Gradient Fields as Computational
                Topology Primitives for Self-Organising Neural Architectures}},
  year      = 2026,
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.XXXXXXX},
  url       = {https://doi.org/10.5281/zenodo.XXXXXXX},
  orcid     = {0000-0002-3315-7907},
  note      = {Maya-Morphe Series, Paper 1}
}
```

---

## About

Venkatesh Swaminathan is an independent researcher and founder of Nexus Learning Labs, Bengaluru (UDYAM-KR-02-0122422), pursuing M.Sc. Data Science & AI at BITS Pilani (expected Dec 2027).

ORCID: 0000-0002-3315-7907 | GitHub: venky2099 | venkateshswaminathaniyer@gmail.com

---

*MayaNexusVS2026NLL_Bengaluru_Narasimha · ORCID: 0000-0002-3315-7907 · UDYAM-KR-02-0122422*
