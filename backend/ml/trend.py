"""
backend/ml/trend.py

Learning Trend (T) component of the Cognitive Readiness Score.

FIXES CR5 (peer review packet): the legacy `_analyze_trend()` in
adaptive_engine.py returned one of three strings ("declining"/"stable"/
"improving") with an asymmetric effect (declining -> -1 modifier,
improving -> no bonus at all), which does not match the paper's Table I,
where T is encoded as a continuous value in {-1, 0, +1} and then rescaled
via T_rescaled = (T + 1) / 2 so it lies in [0,1] like every other CRS
component (this is also the exact fix the review packet's §14 "Concrete
Fixes" recommends).

This module computes a continuous slope (moving-average slope of recent
scores, in percentage-points per assessment), saturates it into [-1, 1],
and applies the same rescaling the paper specifies — so manuscript and
code now agree on both representation and behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from config.crs_config import CRS_CONFIG, TrendConfig


@dataclass(frozen=True)
class TrendResult:
    trend_raw: float  # in [-1, 1], matching the paper's Table I encoding
    trend_score: float  # rescaled to [0,1] via (trend_raw + 1) / 2 — this is "T" in CRS
    label: str  # "improving" | "stable" | "declining" (for display/explanations only)
    slope: float  # raw slope, percentage-points per assessment, before saturation
    window_used: int
    explanation: str


def _slope(scores: Sequence[float]) -> float:
    """
    Ordinary least-squares slope of `scores` against assessment index
    (0, 1, 2, ...). Equivalent to a simple linear regression trend line —
    one of the two approaches Phase 6 explicitly allows (the other being a
    moving-average slope, which this approximates well for short windows).
    """
    n = len(scores)
    if n < 2:
        return 0.0

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(scores) / n

    numerator = sum((xs[i] - mean_x) * (scores[i] - mean_y) for i in range(n))
    denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator


def compute_trend(
    recent_scores_pct: Optional[Sequence[float]] = None,
    config: TrendConfig = CRS_CONFIG.trend,
) -> TrendResult:
    """
    Compute the Learning Trend (T) component.

    Args:
        recent_scores_pct: most-recent-last list of assessment scores as
            percentages (0-100). Only the last `config.window_size` are used.
        config: TrendConfig (window size, slope saturation point).

    Returns:
        TrendResult with `trend_score` already rescaled to [0,1] — this is
        the value to feed directly into CRS's weighted sum as "T".
    """
    if not recent_scores_pct or len(recent_scores_pct) < 2:
        return TrendResult(
            trend_raw=0.0,
            trend_score=0.5,  # (0 + 1) / 2 — neutral, matches paper's rescaling
            label="stable",
            slope=0.0,
            window_used=len(recent_scores_pct) if recent_scores_pct else 0,
            explanation="Fewer than 2 historical scores — trend defaults to stable/neutral.",
        )

    window: List[float] = list(recent_scores_pct[-config.window_size:])
    raw_slope = _slope(window)

    # Saturate slope into [-1, 1] using the configured saturation point.
    trend_raw = max(-1.0, min(1.0, raw_slope / config.slope_saturation))
    trend_score = (trend_raw + 1.0) / 2.0  # paper's Eq.: T_rescaled = (T + 1) / 2

    if trend_raw > 0.15:
        label = "improving"
    elif trend_raw < -0.15:
        label = "declining"
    else:
        label = "stable"

    return TrendResult(
        trend_raw=round(trend_raw, 4),
        trend_score=round(trend_score, 4),
        label=label,
        slope=round(raw_slope, 3),
        window_used=len(window),
        explanation=(
            f"Linear-regression slope over last {len(window)} assessment(s) = "
            f"{raw_slope:+.2f} pct-pts/assessment -> saturated T={trend_raw:+.2f} "
            f"-> rescaled to {trend_score:.2f} ('{label}')."
        ),
    )
