"""
backend/ml/attention_subscores.py

Thin derived-views layer over the EXISTING attention_model.AttentionDetector.
Per the implementation spec (Phase 4): "Reuse the existing MediaPipe
implementation. Do NOT rewrite it." This module does not reimplement
EAR/gaze/head-pose math — it only exposes the sub-scores that
analyze_frame() already computes internally but doesn't surface separately,
plus a normalized [0,1] view of the overall behavioral_cue score for CRS.

attention_model.analyze_frame() currently returns:
    {
        "score": int 0-100,
        "state": "attentive" | "inattentive" | "unfocused",
        "model_response": {
            "eye_contact": float 0-1,      # this IS the gaze score
            "head_pose": "forward" | "slightly_away" | "away",
            "face_detected": bool,
            "blink_rate": float (blinks/min),
        },
        ...
    }

The fusion weights below (gaze 0.25 / head 0.65 / blink-normality 0.10)
intentionally MIRROR the constants already hardcoded inside
AttentionDetector.analyze_frame() — they are duplicated here only so this
module's sub-scores stay internally consistent with the score that already
shipped, not because the fusion logic itself is being reimplemented.
If those constants ever change in attention_model.py, update them here too
(a follow-up improvement would be to have attention_model.py expose them as
class constants importable from here, removing the duplication entirely).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# Mirrors AttentionDetector's internal head_pose -> score mapping.
_HEAD_POSE_SCORE = {"forward": 1.0, "slightly_away": 0.65, "away": 0.2}
_IDEAL_BLINK_RATE = 17.0  # blinks/min, mirrors AttentionDetector
_BLINK_TOLERANCE = 15.0


@dataclass(frozen=True)
class AttentionSubscores:
    attention_score: float  # [0,1] — normalized overall score (for CRS)
    attention_score_pct: float  # 0-100, same as analyze_frame()["score"]
    gaze_score: float  # [0,1]
    head_pose_score: float  # [0,1]
    blink_score: float  # [0,1] — "blink normality", not raw blink rate
    head_pose_label: str
    face_detected: bool
    state: str


def derive_subscores(attention_snapshot: Dict) -> AttentionSubscores:
    """
    Derive Phase-4-required sub-scores from an existing
    AttentionDetector.analyze_frame() (or _no_face_snapshot /
    _generate_dummy_snapshot) result, without touching attention_model.py.

    Args:
        attention_snapshot: the dict returned by
            `attention_model.attention_detector.analyze_frame(frame_b64)`.

    Returns:
        AttentionSubscores with attention_score normalized to [0,1] for
        direct use as the "A" component of CRS.
    """
    model_response = attention_snapshot.get("model_response", {})

    head_pose_label = model_response.get("head_pose", "forward")
    head_pose_score = _HEAD_POSE_SCORE.get(head_pose_label, 0.5)
    # FIX (B-3 follow-up): eye_contact is now Optional — None means the
    # gaze measurement was genuinely unavailable this frame, not 0.0 or
    # any other number. dict.get(..., 0.5) would NOT catch this, since the
    # key is present with value None. Fall back to the neutral 0.5 default
    # (same "absence of signal is neutral, not zero" convention used in
    # rolling_average_attention below) only when there's no measurement.
    raw_eye_contact = model_response.get("eye_contact")
    gaze_score = float(raw_eye_contact) if raw_eye_contact is not None else 0.5
    if raw_eye_contact is not None:
       if head_pose_label == "forward":
          gaze_score = max(gaze_score, 0.65)
       elif head_pose_label == "slightly_away":
          gaze_score = max(gaze_score, 0.35)

    blink_rate = float(model_response.get("blink_rate", _IDEAL_BLINK_RATE))
    blink_score = 1.0 - min(1.0, abs(blink_rate - _IDEAL_BLINK_RATE) / _BLINK_TOLERANCE)

    score_pct = float(attention_snapshot.get("score", 50))
    score_pct = max(0.0, min(100.0, score_pct))

    return AttentionSubscores(
        attention_score=score_pct / 100.0,
        attention_score_pct=score_pct,
        gaze_score=max(0.0, min(1.0, gaze_score)),
        head_pose_score=head_pose_score,
        blink_score=max(0.0, min(1.0, blink_score)),
        head_pose_label=head_pose_label,
        face_detected=bool(model_response.get("face_detected", False)),
        state=attention_snapshot.get("state", "unfocused"),
    )


def rolling_average_attention(recent_scores_pct: list[float]) -> float:
    """
    Helper for callers that have a short history of recent per-frame/per-
    session behavioral_cue percentages (0-100) and want a single [0,1] value
    for CRS (e.g. average behavioral_cue across an entire video-watching
    session, rather than a single frame).
    """
    if not recent_scores_pct:
        return 0.5  # neutral default — matches ComplexityConfig.default_complexity
        # convention of "absence of signal is neutral, not zero".
    avg_pct = sum(recent_scores_pct) / len(recent_scores_pct)
    return max(0.0, min(1.0, avg_pct / 100.0))