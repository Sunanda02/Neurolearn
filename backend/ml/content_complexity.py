"""
backend/ml/content_complexity.py

Content Complexity (C) component of the Cognitive Readiness Score.

FIXES CR2 (peer review packet): this component did not exist anywhere in
the codebase — determine_difficulty() took no complexity argument, and
routers/content.py is an unrelated web-scraping course-content generator.
This module implements the pipeline Phase 7 specifies:

    Lecture Transcript -> Sentence Segmentation -> Readability Metrics ->
    Technical Vocabulary -> Semantic Complexity (deferred — see note below)
    -> Normalized Complexity Score

No new heavy NLP dependency is introduced (no spaCy/sentence-transformers)
so this doesn't touch requirements.txt beyond what's already there —
readability is computed with a standard syllable-counting heuristic, which
is the same approach textstat-style libraries use under the hood. A true
embedding-based semantic-complexity signal (the fifth bullet in Phase 7's
list) is flagged as a documented follow-up rather than faked: an empty/
disabled embedding score quietly contributing zero would be a second,
smaller version of the exact CR2 problem this module fixes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from config.crs_config import CRS_CONFIG, ComplexityConfig

# Small, illustrative technical-vocabulary seed list. This is intentionally
# domain-general (CS/STEM leaning, matching NeuroLearn's current dummy
# course content) rather than exhaustive. Treat as configurable, not final —
# a real deployment should load this from a per-course or per-subject list
# rather than a single hardcoded set, otherwise this module inherits the
# same "secretly hardcoded to one topic" problem the review packet flagged
# for the FLAN-T5 fallback question bank (MJ3).
_DEFAULT_TECHNICAL_TERMS = {
    "algorithm", "function", "variable", "recursion", "asynchronous",
    "synchronous", "middleware", "framework", "compiler", "runtime",
    "polymorphism", "inheritance", "encapsulation", "abstraction",
    "concurrency", "thread", "process", "kernel", "protocol", "latency",
    "throughput", "architecture", "dependency", "instantiate", "iterator",
    "closure", "callback", "promise", "component", "render", "state",
    "props", "hook", "endpoint", "schema", "query", "index", "normalize",
    "gradient", "tensor", "embedding", "transformer", "inference",
    "regression", "classifier", "heuristic", "optimization", "complexity",
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouyAEIOUY]+")


@dataclass(frozen=True)
class ComplexityResult:
    complexity_score: float  # [0,1], higher = more complex/difficult content
    flesch_reading_ease: Optional[float]  # raw, 0-100 (higher = easier), None if no text
    avg_sentence_length: Optional[float]  # words per sentence
    technical_density: Optional[float]  # fraction of words matching technical terms
    sentence_count: int
    word_count: int
    explanation: str


def _count_syllables(word: str) -> int:
    """Heuristic syllable counter: counts vowel groups, with the standard
    silent-trailing-'e' adjustment. Same approach used internally by
    textstat-style libraries; not perfectly linguistically accurate but
    stable and dependency-free."""
    word = word.lower()
    groups = _VOWEL_GROUP_RE.findall(word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _segment_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    sentences = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


def compute_content_complexity(
    transcript_text: Optional[str],
    technical_terms: Optional[set[str]] = None,
    config: ComplexityConfig = CRS_CONFIG.complexity,
) -> ComplexityResult:
    """
    Compute the Content Complexity (C) component from transcript text.

    Args:
        transcript_text: the transcript segment(s) the student has watched
            so far. If None/empty, returns a neutral default (per Phase 7's
            "Return ... Complexity Score" requirement, absence of a
            transcript should not silently bias CRS toward easy or hard).
        technical_terms: optional override of the technical-vocabulary set;
            defaults to `_DEFAULT_TECHNICAL_TERMS`.
        config: ComplexityConfig (sub-signal weights, default value).

    Returns:
        ComplexityResult with `complexity_score` in [0,1] (higher = harder).
    """
    if not transcript_text or not transcript_text.strip():
        return ComplexityResult(
            complexity_score=config.default_complexity,
            flesch_reading_ease=None,
            avg_sentence_length=None,
            technical_density=None,
            sentence_count=0,
            word_count=0,
            explanation=(
                f"No transcript text available — using neutral default "
                f"complexity of {config.default_complexity:.2f}."
            ),
        )

    terms = technical_terms if technical_terms is not None else _DEFAULT_TECHNICAL_TERMS

    sentences = _segment_sentences(transcript_text)
    words = _WORD_RE.findall(transcript_text)
    word_count = len(words)
    sentence_count = max(1, len(sentences))  # avoid div-by-zero for one-fragment input

    if word_count == 0:
        return ComplexityResult(
            complexity_score=config.default_complexity,
            flesch_reading_ease=None,
            avg_sentence_length=None,
            technical_density=None,
            sentence_count=len(sentences),
            word_count=0,
            explanation="Transcript contained no recognizable words — using neutral default.",
        )

    syllables = sum(_count_syllables(w) for w in words)

    # ── Flesch Reading Ease (standard formula; 0-100, higher = easier) ──
    flesch = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllables / word_count)
    flesch_clamped = max(0.0, min(100.0, flesch))
    readability_complexity = 1.0 - (flesch_clamped / 100.0)  # invert: low ease = high complexity

    # ── Average sentence length, saturating at 30 words/sentence ──
    avg_sentence_len = word_count / sentence_count
    sentence_len_complexity = max(0.0, min(1.0, avg_sentence_len / 30.0))

    # ── Technical vocabulary density ──
    lower_words = [w.lower() for w in words]
    technical_hits = sum(1 for w in lower_words if w in terms)
    technical_density = technical_hits / word_count

    # Density of even 10% domain terms is already a strong signal, so scale
    # up before clamping rather than treating density linearly to 1.0.
    technical_complexity = max(0.0, min(1.0, technical_density / 0.10))

    # ── Weighted combination (weights need not sum to 1 — renormalize) ──
    w_r = config.readability_weight
    w_t = config.technical_density_weight
    w_s = config.sentence_length_weight
    weight_total = max(1e-6, w_r + w_t + w_s)

    complexity = (
        w_r * readability_complexity + w_t * technical_complexity + w_s * sentence_len_complexity
    ) / weight_total
    complexity = max(0.0, min(1.0, complexity))

    explanation = (
        f"Flesch Reading Ease={flesch_clamped:.1f} (complexity contribution="
        f"{readability_complexity:.2f}); avg sentence length={avg_sentence_len:.1f} words "
        f"(contribution={sentence_len_complexity:.2f}); technical term density="
        f"{technical_density:.1%} (contribution={technical_complexity:.2f}) "
        f"-> combined complexity={complexity:.2f}."
    )

    return ComplexityResult(
        complexity_score=round(complexity, 4),
        flesch_reading_ease=round(flesch_clamped, 1),
        avg_sentence_length=round(avg_sentence_len, 1),
        technical_density=round(technical_density, 4),
        sentence_count=len(sentences),
        word_count=word_count,
        explanation=explanation,
    )
