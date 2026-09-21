"""
backend/ml/performance.py

Performance (P) component of the Cognitive Readiness Score.

P is a recency-weighted rolling average of recent assessment scores,
normalized to [0,1]. This is intentionally the simplest of the five CRS
components — it formalizes what `current_score` already meant informally
in the legacy adaptive_engine.py rule cascade, but as a proper windowed
average rather than a single most-recent score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from config.crs_config import CRS_CONFIG, PerformanceConfig


@dataclass(frozen=True)
class PerformanceResult:
    score: float  # normalized [0,1]
    score_pct: float  # same value, as a 0-100 percentage (for display/logging)
    window_used: int  # how many historical scores actually contributed
    explanation: str


def compute_performance(
    recent_scores_pct: Optional[Sequence[float]] = None,
    config: PerformanceConfig = CRS_CONFIG.performance,
) -> PerformanceResult:
    """
    Compute the Performance (P) component.

    Args:
        recent_scores_pct: most-recent-last list of assessment scores as
            percentages (0-100). Only the last `config.window_size` entries
            are used. May be None or empty (e.g. a brand-new student).
        config: PerformanceConfig (window size, recency weighting, default).

    Returns:
        PerformanceResult with `score` normalized to [0,1].
    """
    if not recent_scores_pct:
        return PerformanceResult(
            score=config.default_score_pct / 100.0,
            score_pct=config.default_score_pct,
            window_used=0,
            explanation=(
                f"No assessment history available — using default baseline "
                f"of {config.default_score_pct:.0f}%."
            ),
        )

    window: List[float] = list(recent_scores_pct[-config.window_size:])
    n = len(window)

    if n == 1:
        weights = [1.0]
    else:
        # Linear ramp from 1.0 (oldest in window) to recency_weight (most recent).
        step = (config.recency_weight - 1.0) / (n - 1)
        weights = [1.0 + step * i for i in range(n)]

    weighted_sum = sum(w * s for w, s in zip(weights, window))
    weight_total = sum(weights)
    avg_pct = weighted_sum / weight_total

    avg_pct = max(0.0, min(100.0, avg_pct))

    return PerformanceResult(
        score=avg_pct / 100.0,
        score_pct=avg_pct,
        window_used=n,
        explanation=(
            f"Recency-weighted average of last {n} assessment(s) "
            f"(window={config.window_size}, recency_weight={config.recency_weight}) "
            f"= {avg_pct:.1f}%."
        ),
    )
