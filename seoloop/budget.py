"""Stop rule: a run ends after N tasks or after $X, whichever comes first."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunBudget:
    max_usd: float = 8.0
    max_tasks: int = 3
    spent_usd: float = 0.0
    tasks_done: int = 0
    ledger: list = field(default_factory=list)

    def charge(self, label: str, usd: float | None) -> None:
        usd = float(usd or 0.0)
        self.spent_usd += usd
        self.ledger.append((label, round(usd, 6)))

    def task_finished(self) -> None:
        self.tasks_done += 1

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.max_usd - self.spent_usd)

    def stop_reason(self) -> str | None:
        if self.spent_usd >= self.max_usd:
            return f"budget: ${self.spent_usd:.2f} of ${self.max_usd:.2f} spent"
        if self.tasks_done >= self.max_tasks:
            return f"tasks: {self.tasks_done} of {self.max_tasks} done"
        return None

    def can_afford(self, estimate_usd: float) -> bool:
        """True if a step estimated at `estimate_usd` still fits the run budget."""
        return self.stop_reason() is None and self.spent_usd + estimate_usd <= self.max_usd
