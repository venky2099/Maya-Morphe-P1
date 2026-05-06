"""
prana.py
========
Metabolic energy budget for Maya-Morphe voltage propagation.

Prana limits how much gradient propagation can occur per timestep.
When depleted, diffusion slows. Prana recovers during low-activity periods.

This maps directly to Maya-Prana (P9) which governed synaptic metabolic cost.
The computational primitive is identical — only the substrate changes.

PRANA_COST_RATE = 0.002315 (ORCID magic number)

Nexus Learning Labs | ORCID: 0000-0002-3315-7907
"""
from .constants import PRANA_INITIAL_BUDGET, PRANA_RECOVERY_RATE, PRANA_COST_RATE


class PranaEngine:
    """
    Tracks and enforces the Prana energy budget across timesteps.
    """

    def __init__(self):
        self.budget = PRANA_INITIAL_BUDGET
        self.history = [PRANA_INITIAL_BUDGET]

    def consume(self, cost: float) -> float:
        """
        Consume Prana proportional to voltage propagation activity.
        Returns the effective multiplier on diffusion (0.0 to 1.0).
        """
        self.budget = max(0.0, self.budget - cost)
        self.history.append(self.budget)
        effective_multiplier = self.budget / PRANA_INITIAL_BUDGET
        return effective_multiplier

    def recover(self, activity_level: float):
        """
        Recover Prana during low-activity periods.
        Higher activity = slower recovery (biological realism).
        """
        recovery = PRANA_RECOVERY_RATE * (1.0 - activity_level)
        self.budget = min(PRANA_INITIAL_BUDGET, self.budget + recovery)

    def is_depleted(self) -> bool:
        return self.budget < 0.05

    def reset(self):
        self.budget = PRANA_INITIAL_BUDGET
        self.history = [PRANA_INITIAL_BUDGET]
