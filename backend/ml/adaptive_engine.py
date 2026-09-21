"""
backend/ml/adaptive_engine.py

Adaptive Engine — Phase 9 of the implementation spec.

FIXES CR1 (peer review packet) at the integration point: previously,
determine_difficulty() ran a rule cascade (score baseline + integer
modifiers, clamped to 3 tiers). It now computes the Cognitive Readiness
Score (CRS) via ml/crs.py and selects difficulty from configurable CRS
thresholds (config/crs_config.py: DifficultyThresholds), per Phase 9:

    CRS > hard_threshold   -> "hard"
    medium..hard           -> "medium"
    CRS < medium_threshold -> "easy"

BACKWARD COMPATIBILITY: the public method signatures of
`determine_difficulty()` and `get_initial_difficulty()` are UNCHANGED, so
routers/assessment.py does not need to change to pick this up. The legacy
rule cascade is preserved as `_determine_difficulty_legacy()` and is still
reachable by setting `CRS_CONFIG.crs_enabled = False` (e.g. for an A/B
comparison between the two engines, which is one of the three evaluation
options the review packet's §5 suggests) — it is not deleted, per the
spec's "no placeholder implementations ... backward compatible" standard.

NOTE on history: `_history` remains an in-memory dict for this phase,
identical to the legacy engine's storage. This still does not survive a
process restart. The peer review packet's CR1/MJ4 concerns and the
implementation spec's Phase 8 (persistent CRS history) call for moving
this into TinyDB — that is intentionally NOT done in this file, since it
requires a schema change (Phase 13) and new persistence functions
(Phase 8), which are the next stop-point, not bundled into this change.
`compute_crs()` itself is storage-agnostic — it accepts history as a plain
list — so swapping the source from `self._history` to a TinyDB-backed
query later is a small, localized change in this file only.
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from config.crs_config import CRS_CONFIG
from ml.crs import compute_crs, CRSResult


class AdaptiveEngine:

    DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

    # ── Legacy rule-cascade constants (kept for the CRS-disabled fallback
    # path only — do not use these in the CRS-driven path below). ──
    UPGRADE_THRESHOLD = 80
    MAINTAIN_THRESHOLD = 50
    LOW_ATTENTION_THRESHOLD = 40
    HIGH_ATTENTION_BONUS_THRESHOLD = 85
    SPEED_GUESS_RATIO = 0.3
    THOUGHTFUL_RATIO_LOW = 0.5
    THOUGHTFUL_RATIO_HIGH = 0.8

    def __init__(self):
        # In-memory history (Phase 8 will move this to TinyDB — see module
        # docstring). Each entry: {score, difficulty, behavioral_cue, time_spent,
        # time_limit, was_correct, timestamp}.
        self._history: dict[str, list[dict]] = {}
        logger.info(
            f"Adaptive engine initialized (crs_enabled={CRS_CONFIG.crs_enabled})"
        )

    # ──────────────────────────────────────────────────────────────────
    # Public API — UNCHANGED signatures (backward compatible)
    # ──────────────────────────────────────────────────────────────────

    def determine_difficulty(
        self,
        student_id: str,
        current_score: float,
        attention_score: Optional[float],
        time_spent: int,
        time_limit: int,
        previous_difficulty: str = "medium",
        previous_scores: Optional[list[float]] = None,
        transcript_text: Optional[str] = None,
        was_correct: Optional[bool] = None,
    ) -> dict:
        """
        Determine optimal next difficulty.

        Two NEW optional kwargs are added at the end (`transcript_text`,
        `was_correct`) so existing callers that don't pass them keep working
        unchanged (they fall back to neutral defaults inside compute_crs),
        while routers/assessment.py can be updated to actually pass a real
        transcript and correctness flag in a follow-up change (Phase 11/13)
        without breaking this signature again.

        Returns the same top-level keys the legacy engine returned
        (`performance_trend`, `recommended_action`,
        `next_assessment_difficulty`, `strength_areas`, `weak_areas`,
        `_debug`), plus a new `crs` block with the full CRS breakdown, so
        existing frontend code that only reads the old keys is unaffected.
        """
        if not CRS_CONFIG.crs_enabled:
            # FIX (D-4 follow-up): attention_score may now genuinely be
            # None; the rule-cascade fallback below does direct numeric
            # comparisons on it, so it needs a concrete value here too —
            # same neutral-default convention as compute_crs uses.
            return self._determine_difficulty_legacy(
                student_id, current_score,
                attention_score if attention_score is not None else 50.0,
                time_spent, time_limit, previous_difficulty, previous_scores,
            )

        scores_history = self._scores_for(student_id, previous_scores, current_score)

        crs_result: CRSResult = compute_crs(
            recent_scores_pct=scores_history,
            attention_score_pct=attention_score,
            time_spent=time_spent,
            time_limit=time_limit,
            was_correct=was_correct,
            transcript_text=transcript_text,
        )

        trend_label = crs_result.detail["trend"]["label"]
        # FIX (D-4 follow-up): attention_score may now genuinely be None
        # (no camera data at all) — compute_crs above already handles that
        # correctly and records it in crs_result.detail["behavioral_cue"]
        # ["source"]. _analyze_areas is purely cosmetic (strength/weakness
        # labels for display), so it gets a neutral display value here;
        # this does NOT affect the stored decision's source flag, which
        # comes from the untouched `attention_score` passed to compute_crs.
        strengths, weaknesses = self._analyze_areas(
            current_score, attention_score if attention_score is not None else 50.0
        )
        recommended_action = self._recommended_action(crs_result.difficulty, trend_label)

        self._record_history(
            student_id, current_score, crs_result.difficulty, attention_score,
            time_spent=time_spent, time_limit=time_limit, was_correct=was_correct,
        )

        return {
            "performance_trend": trend_label,
            "recommended_action": recommended_action,
            "next_assessment_difficulty": crs_result.difficulty,
            "strength_areas": strengths,
            "weak_areas": weaknesses,
            "crs": {
                "score": crs_result.crs,
                "score_pct": crs_result.crs_pct,
                "components": crs_result.components.as_dict(),
                "weights_used": crs_result.weights_used,
                "explanation": crs_result.explanation,
                "detail": crs_result.detail,
            },
            "_debug": {
                "engine": "crs",
                "reason": crs_result.explanation,
            },
        }

    def get_initial_difficulty(
        self,
        student_id: str,
        attention_score: Optional[float],
        previous_score: Optional[float] = None,
        previous_scores: Optional[list[float]] = None,
        transcript_text: Optional[str] = None,
    ) -> dict:
        """
        Determine initial assessment difficulty before quiz starts.
        Signature UNCHANGED for backward compatibility.
        """
        if not CRS_CONFIG.crs_enabled:
            return self._get_initial_difficulty_legacy(
                student_id,
                attention_score if attention_score is not None else 50.0,
                previous_score,
            )

        scores_history = self._history.get(student_id, [])
        # The optional explicit history is supplied by the durable research
        # store.  This keeps initial MCRF decisions reproducible after a
        # process restart while preserving the original call signature for
        # existing callers.
        recent_scores = list(previous_scores[-5:]) if previous_scores else [h["score"] for h in scores_history[-5:]]
        if previous_score is not None and (not recent_scores or recent_scores[-1] != previous_score):
            recent_scores = recent_scores + [previous_score]

        crs_result: CRSResult = compute_crs(
            recent_scores_pct=recent_scores or None,
            attention_score_pct=attention_score,
            transcript_text=transcript_text,
            # No timing/correctness yet — compute_crs defaults Integrity to
            # its neutral maximum (see crs.py docstring) so a student isn't
            # penalized before answering anything.
        )

        reason = (
            f"Initial CRS={crs_result.crs:.2f} -> '{crs_result.difficulty}'. "
            f"{crs_result.explanation}"
        )

        return {
            "difficulty": crs_result.difficulty,
            "adaptive_metadata": {
                "previous_score": previous_score,
                "adjusted_difficulty": crs_result.difficulty,
                "reason": reason,
                "crs": crs_result.crs,
            },
            "crs": {
                "score": crs_result.crs,
                "score_pct": crs_result.crs_pct,
                "components": crs_result.components.as_dict(),
                "weights_used": crs_result.weights_used,
                "explanation": crs_result.explanation,
                "detail": crs_result.detail,
            },
        }

    # ──────────────────────────────────────────────────────────────────
    # Helpers (CRS-driven path)
    # ──────────────────────────────────────────────────────────────────

    def _scores_for(
        self,
        student_id: str,
        previous_scores: Optional[list[float]],
        current_score: float,
    ) -> list[float]:
        """Build the score history list (most-recent-last) used by both
        Performance and Trend, mirroring the legacy engine's source-of-truth
        precedence: explicit `previous_scores` argument wins over the
        in-memory history, then the current score is appended."""
        if previous_scores:
            scores = list(previous_scores[-5:])
        else:
            scores = [h["score"] for h in self._history.get(student_id, [])[-5:]]
        scores.append(current_score)
        return scores

    def _recommended_action(self, difficulty: str, trend_label: str) -> str:
        action_messages = {
            ("hard", "improving"): "Outstanding! You're mastering this material. Moving to advanced content.",
            ("hard", "stable"): "Great performance! Continue with challenging material.",
            ("hard", "declining"): "You've been doing well but recent scores dipped. Let's reinforce with some review.",
            ("medium", "improving"): "Good progress! Keep building — you'll unlock harder content soon.",
            ("medium", "stable"): "Solid and steady. Keep practicing at this level.",
            ("medium", "declining"): "You seem to be struggling a bit. Let's reinforce the fundamentals.",
            ("easy", "improving"): "You're getting stronger! This easier content will help build confidence.",
            ("easy", "stable"): "Take your time to build a strong foundation. You're doing fine!",
            ("easy", "declining"): "Don't worry! Let's go through the basics again. Rewatch the video if needed.",
        }
        return action_messages.get((difficulty, trend_label), "Keep learning! Every step counts.")

    def _analyze_areas(self, score: float, behavioral_cue: float) -> tuple[list[str], list[str]]:
        """Unchanged from the legacy engine — not part of CRS, just display copy."""
        strengths = []
        weaknesses = []

        if score >= 80:
            strengths.extend(["Core Concepts", "Problem Solving"])
        elif score >= 60:
            strengths.append("Basic Recognition")
            weaknesses.append("Applied Knowledge")
        else:
            weaknesses.extend(["Core Concepts", "Deep Understanding"])

        if behavioral_cue >= 70:
            strengths.append("Focus & Engagement")
        elif behavioral_cue < 40:
            weaknesses.append("Sustained Behavioral Cue")

        return strengths, weaknesses

    def _record_history(
        self,
        student_id: str,
        score: float,
        difficulty: str,
        behavioral_cue: float,
        time_spent: Optional[float] = None,
        time_limit: Optional[float] = None,
        was_correct: Optional[bool] = None,
    ):
        if student_id not in self._history:
            self._history[student_id] = []

        self._history[student_id].append({
            "score": score,
            "difficulty": difficulty,
            "behavioral_cue": behavioral_cue,
            "time_spent": time_spent,
            "time_limit": time_limit,
            "was_correct": was_correct,
            "timestamp": time.time(),
        })

        self._history[student_id] = self._history[student_id][-20:]

    # ──────────────────────────────────────────────────────────────────
    # Legacy rule cascade — preserved verbatim, reachable only when
    # CRS_CONFIG.crs_enabled is False. Do not extend this path; extend
    # the CRS modules instead.
    # ──────────────────────────────────────────────────────────────────

    def _determine_difficulty_legacy(
        self,
        student_id: str,
        current_score: float,
        attention_score: float,
        time_spent: int,
        time_limit: int,
        previous_difficulty: str = "medium",
        previous_scores: Optional[list[float]] = None,
    ) -> dict:
        if current_score >= self.UPGRADE_THRESHOLD:
            baseline = self._level_up(previous_difficulty)
            score_action = "upgrade"
        elif current_score >= self.MAINTAIN_THRESHOLD:
            baseline = previous_difficulty
            score_action = "maintain"
        else:
            baseline = self._level_down(previous_difficulty)
            score_action = "downgrade"

        attention_modifier = 0
        if attention_score < self.LOW_ATTENTION_THRESHOLD:
            attention_modifier = -1
        elif attention_score >= self.HIGH_ATTENTION_BONUS_THRESHOLD and current_score >= 70:
            attention_modifier = 0

        time_ratio = time_spent / max(time_limit, 1)
        time_modifier = 0
        time_note = ""
        if time_ratio < self.SPEED_GUESS_RATIO and current_score < 70:
            time_modifier = -1
            time_note = "Very fast completion with low score suggests rapid completion"
        elif self.THOUGHTFUL_RATIO_LOW <= time_ratio <= self.THOUGHTFUL_RATIO_HIGH:
            time_note = "Thoughtful pace — good engagement"

        trend = self._analyze_trend_legacy(student_id, current_score, previous_scores)
        trend_modifier = 0
        if trend == "declining" and score_action != "downgrade":
            trend_modifier = -1

        current_idx = self.DIFFICULTY_LEVELS.index(baseline)
        total_modifier = attention_modifier + time_modifier + trend_modifier
        final_idx = max(0, min(2, current_idx + total_modifier))
        next_difficulty = self.DIFFICULTY_LEVELS[final_idx]

        reasons = [f"Score: {current_score:.0f}% -> {score_action}"]
        if attention_modifier != 0:
            reasons.append(f"Behavioral Cue: {attention_score:.0f}% (low -> easier)")
        if time_modifier != 0:
            reasons.append(time_note)
        if trend_modifier != 0:
            reasons.append(f"Trend: {trend} -> reducing difficulty")
        reason = " | ".join(reasons)

        strengths, weaknesses = self._analyze_areas(current_score, attention_score)
        recommended_action = self._recommended_action(next_difficulty, trend)

        self._record_history(student_id, current_score, next_difficulty, attention_score)

        return {
            "performance_trend": trend,
            "recommended_action": recommended_action,
            "next_assessment_difficulty": next_difficulty,
            "strength_areas": strengths,
            "weak_areas": weaknesses,
            "_debug": {
                "engine": "legacy_rule_cascade",
                "baseline": baseline,
                "modifiers": {
                    "behavioral_cue": attention_modifier,
                    "time": time_modifier,
                    "trend": trend_modifier,
                },
                "reason": reason,
                "time_ratio": round(time_ratio, 2),
            },
        }

    def _get_initial_difficulty_legacy(
        self,
        student_id: str,
        attention_score: float,
        previous_score: Optional[float] = None,
    ) -> dict:
        difficulty = "medium"
        reason = "Default medium difficulty for first attempt"

        if previous_score is not None:
            if previous_score >= 80:
                difficulty = "hard"
                reason = f"Previous score {previous_score:.0f}% -> hard difficulty"
            elif previous_score >= 50:
                difficulty = "medium"
                reason = f"Previous score {previous_score:.0f}% -> medium difficulty"
            else:
                difficulty = "easy"
                reason = f"Previous score {previous_score:.0f}% -> easy for reinforcement"

        if attention_score < self.LOW_ATTENTION_THRESHOLD and difficulty != "easy":
            old_diff = difficulty
            difficulty = self._level_down(difficulty)
            reason += f" | Low behavioral_cue ({attention_score:.0f}%) -> {old_diff} reduced to {difficulty}"

        return {
            "difficulty": difficulty,
            "adaptive_metadata": {
                "previous_score": previous_score,
                "adjusted_difficulty": difficulty,
                "reason": reason,
            },
        }

    def _level_up(self, current: str) -> str:
        idx = self.DIFFICULTY_LEVELS.index(current)
        return self.DIFFICULTY_LEVELS[min(idx + 1, 2)]

    def _level_down(self, current: str) -> str:
        idx = self.DIFFICULTY_LEVELS.index(current)
        return self.DIFFICULTY_LEVELS[max(idx - 1, 0)]

    def _analyze_trend_legacy(
        self,
        student_id: str,
        current_score: float,
        previous_scores: Optional[list[float]] = None,
    ) -> str:
        history = self._history.get(student_id, [])
        scores = [h["score"] for h in history[-5:]]
        if previous_scores:
            scores = previous_scores[-5:]
        scores.append(current_score)

        if len(scores) < 2:
            return "stable"

        recent = scores[-3:] if len(scores) >= 3 else scores
        if all(recent[i] <= recent[i - 1] for i in range(1, len(recent))):
            return "declining"
        elif all(recent[i] >= recent[i - 1] for i in range(1, len(recent))):
            return "improving"
        else:
            avg_change = sum(recent[i] - recent[i - 1] for i in range(1, len(recent))) / (len(recent) - 1)
            if avg_change > 5:
                return "improving"
            elif avg_change < -5:
                return "declining"
            return "stable"


# ── Singleton — unchanged ──
adaptive_engine = AdaptiveEngine()