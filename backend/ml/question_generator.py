"""
Generates assessment questions from transcript text using a
provider-agnostic LLM layer (see ml/llm_providers.py — today configured to
Ollama via LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL in .env).

This module owns: prompting, response parsing (JSON-first, with a
labeled-text fallback for models that don't reliably follow the JSON
instruction), content validation (distinct options, transcript grounding,
non-generic, non-duplicate), and the bounded retry budget for a single
question. It does NOT know or care which provider/model is configured —
that is entirely config/llm_config.py + ml/llm_providers.py's concern.

There is deliberately no static-question-bank fallback here: if a valid,
transcript-grounded question cannot be produced, generation raises
QuestionGenerationError (or an LLMProviderError from ml/llm_providers.py)
and the caller (routers/assessment.py) must fail the request clearly. A
research assessment must never silently substitute a generic/static
question for a real, LLM-generated one.
"""

from __future__ import annotations

import json
import re
import uuid
import random
from typing import Optional

from loguru import logger

from config.llm_config import LLM_CONFIG
from ml.llm_providers import LLMProviderError, get_llm_provider


class QuestionGenerationError(Exception):
    """Raised when a valid, transcript-grounded question could not be
    produced after the configured number of attempts (malformed output,
    insufficient transcript grounding, generic/title question, or a
    duplicate). Distinct from LLMProviderError (ml/llm_providers.py), which
    means the provider itself failed (connection/timeout/model missing/
    unparseable HTTP response) rather than "the model answered but the
    content didn't pass validation." Callers must let both propagate into a
    clear backend error — never substitute a static question for either.
    """


class QuestionGenerator:
    """
    Generates assessment MCQs from transcript text via the configured LLM
    provider.

    Difficulty levels:
        - easy:   remember/understand (Bloom's taxonomy)
        - medium: apply/analyze
        - hard:   evaluate/create
    """

    _BLOOMS_MAP = {
        "easy": ["remember", "understand"],
        "medium": ["apply", "analyze"],
        "hard": ["evaluate", "create"],
    }
    _DIFFICULTY_SCORES = {"easy": 0.2, "medium": 0.55, "hard": 0.8}
    _POINTS_MAP = {"easy": 10, "medium": 20, "hard": 30}

    # Temperatures tried in order across the bounded retry budget
    # (LLM_CONFIG.max_generation_attempts) — low first for a focused,
    # faithful-to-the-text answer, rising only if an earlier attempt was
    # rejected, to give a genuinely different draw rather than repeating
    # the same call.
    _TEMPERATURES = [0.2, 0.6, 0.9]

    def __init__(self):
        self.provider = get_llm_provider()

    def generate_questions(
        self,
        transcript_text: str,
        difficulty: str = "medium",
        num_questions: int = 1,
        topic_id: str = "course_001",
        segment_offset: int = 0,
    ) -> list[dict]:
        """
        Generate `num_questions` MCQs from transcript_text.

        Args:
            transcript_text: The video transcript to generate questions from
            difficulty: "easy" | "medium" | "hard" — used as-is; this
                function never computes or changes difficulty (MCRF/LEGACY
                own that entirely, upstream in routers/assessment.py).
            num_questions: How many questions to generate in this call
            topic_id: Course/topic ID for metadata
            segment_offset: Which ~800-char transcript segment to start
                rotating from. Callers generating one question at a time
                (the normal case — see routers/assessment.py) MUST vary
                this per call so the ten questions of an assessment are
                grounded in different parts of the transcript instead of
                all reusing the same first segment.

        Returns:
            List of JSON-serializable question dicts.

        Raises:
            LLMProviderError: the provider itself failed (connection,
                timeout, missing model, unparseable HTTP response).
            QuestionGenerationError: the provider responded, but a valid,
                transcript-grounded, non-duplicate question could not be
                produced within the configured attempt budget.
        """
        questions: list[dict] = []
        seen_question_keys: set[str] = set()

        # Non-overlapping ~800-char segments so different questions are
        # grounded in different parts of what the student actually
        # watched, rather than the whole transcript being dumped into
        # every prompt.
        #
        # FIX (TODO-2): a multi-video study session's transcript_text is
        # the concatenation of each completed video's transcript (see
        # data/database.py get_completed_video_context, which tags each
        # block "[Video <id>]\n<text>"). Naively chopping that flat blob
        # into 800-char segments and picking segment_index = offset %
        # len(segments) meant that whenever the FIRST video's transcript
        # alone was long enough to produce >= 10 segments (common for a
        # normal-length lecture), every one of the ten questions landed
        # inside that first video's segments — later videos' segments
        # were simply never reachable by any offset in [0, 9]. A session
        # with contributing_video_ids = ["v6", "v8"] would then generate
        # questions effectively grounded only in v6.
        #
        # Fix: split per-video first, then interleave round-robin across
        # videos (v6 seg0, v8 seg0, v6 seg1, v8 seg1, ...) before
        # flattening. Now segment_index 0..len(videos)-1 always covers
        # one segment from every completed video before any video
        # repeats, so coverage no longer depends on relative transcript
        # length. Falls back to the previous flat segmentation unchanged
        # when no "[Video ...]" markers are present (single-video/legacy
        # callers passing raw, unmarked transcript text).
        segment_len = 800
        segments = self._segment_transcript(transcript_text, segment_len)

        for i in range(num_questions):
            segment_index = (segment_offset + i) % len(segments)
            segment = segments[segment_index]
            blooms = random.choice(self._BLOOMS_MAP.get(difficulty, ["understand"]))
            logger.info(
                f"Generating question {segment_offset + i + 1}/10 "
                f"(difficulty={difficulty}, transcript segment {segment_index})"
            )
            parsed = self._generate_one_from_segment(segment, difficulty, seen_question_keys)
            key = self._question_key(parsed["question"])
            seen_question_keys.add(key)

            questions.append({
                "id": f"q_gen_{uuid.uuid4().hex[:8]}",
                "type": "mcq",
                "question": parsed["question"],
                "options": parsed["options"],
                "correct_answer": parsed["correct_index"],
                "difficulty": difficulty,
                "points": self._POINTS_MAP.get(difficulty, 20),
                "explanation": parsed["explanation"],
                "topic_id": topic_id,
                "llm_metadata": {
                    "provider": LLM_CONFIG.provider,
                    "model": LLM_CONFIG.model,
                    "generated_from": "video_transcript",
                    "difficulty_score": self._DIFFICULTY_SCORES.get(difficulty, 0.5),
                    "blooms_level": blooms,
                },
                "source": "llm_generated",
            })

        return questions

    # ── TODO-2 fix: per-video-aware segmentation ─────────────────────────

    _VIDEO_MARKER_RE = re.compile(r"(?=\[Video [^\]\n]+\]\n)")

    @classmethod
    def _segment_transcript(cls, transcript_text: str, segment_len: int) -> list[str]:
        """
        Split transcript_text into ~segment_len-char segments, ordered so
        that every completed video contributes a segment before any video
        repeats.

        transcript_text may be a single video's raw transcript (no
        markers) or the multi-video concatenation produced by
        data/database.py get_completed_video_context, which tags each
        block "[Video <id>]\\n<text>" and joins them with a blank line.
        """
        blocks = [b for b in cls._VIDEO_MARKER_RE.split(transcript_text) if b.strip()]
        video_marker_re = re.compile(r"^\[Video [^\]\n]+\]\n")
        is_multi_video = len(blocks) > 1 and all(video_marker_re.match(b) for b in blocks)

        if not is_multi_video:
            # Single video / legacy unmarked transcript — unchanged
            # behavior: one flat sequence of segments.
            flat = [transcript_text[i : i + segment_len] for i in range(0, len(transcript_text), segment_len)]
            return flat or [transcript_text]

        # Segment each video's block independently, then interleave
        # round-robin so segment index 0..N-1 (N = number of videos)
        # always covers one segment per video first.
        per_video_segments = [
            [block[i : i + segment_len] for i in range(0, len(block), segment_len)] or [block]
            for block in blocks
        ]
        interleaved: list[str] = []
        max_len = max(len(segs) for segs in per_video_segments)
        for round_index in range(max_len):
            for segs in per_video_segments:
                if round_index < len(segs):
                    interleaved.append(segs[round_index])
        return interleaved or [transcript_text]

    # ── Generation + bounded retry ──────────────────────────────────────

    def _generate_one_from_segment(
        self, segment: str, difficulty: str, seen_question_keys: set[str]
    ) -> dict:
        """Try, up to LLM_CONFIG.max_generation_attempts times, to get one
        well-formed, non-generic, segment-grounded, non-duplicate question.

        Each attempt uses a different temperature so a rejected attempt is
        a genuinely different draw, not a repeat of the same call. This is
        a small, bounded budget (config default 3) — not the old
        20-retries-per-question loop.
        """
        blooms = random.choice(self._BLOOMS_MAP.get(difficulty, ["understand"]))
        prompt = self._build_prompt(segment, difficulty, blooms)
        last_provider_error: Optional[LLMProviderError] = None
        last_rejection_reason = "no attempts made"

        for attempt in range(LLM_CONFIG.max_generation_attempts):
            temperature = self._TEMPERATURES[min(attempt, len(self._TEMPERATURES) - 1)]
            try:
                raw = self.provider.generate(prompt, temperature=temperature, json_mode=True)
            except LLMProviderError as exc:
                logger.error(f"LLM provider error on attempt {attempt + 1}: {exc}")
                last_provider_error = exc
                continue

            parsed = self._parse_generated_question(raw)
            if not parsed:
                last_rejection_reason = "malformed output"
                logger.warning(f"Question rejected: {last_rejection_reason} (attempt {attempt + 1})")
                continue
            if not self._is_grounded_in_segment(parsed, segment):
                last_rejection_reason = "insufficient transcript grounding"
                logger.warning(f"Question rejected: {last_rejection_reason} (attempt {attempt + 1})")
                continue
            if self._question_key(parsed["question"]) in seen_question_keys:
                last_rejection_reason = "duplicate question"
                logger.warning(f"Question rejected: {last_rejection_reason} (attempt {attempt + 1})")
                continue

            logger.info("Question accepted")
            return parsed

        if last_provider_error is not None:
            # The provider itself is the problem (connection/timeout/model
            # missing/unparseable response) — surface that distinctly so
            # the caller can report it as an infrastructure failure rather
            # than a content-quality one.
            raise last_provider_error

        raise QuestionGenerationError(
            f"Could not produce a valid question after "
            f"{LLM_CONFIG.max_generation_attempts} attempts — last rejection: {last_rejection_reason}"
        )

    # Question-style pool for variety across the 10-question assessment
    # (spec: "avoid generating the same question pattern repeatedly").
    # Since each question is generated in its own call (no shared state
    # needed), one style is drawn at random per call — over 10 calls this
    # naturally mixes styles instead of defaulting to one pattern.
    _QUESTION_STYLES = [
        (
            "scenario/application",
            "Describe a realistic situation where someone needs to apply a concept "
            "from the lesson content, and ask which choice or approach is correct.",
        ),
        (
            "decision",
            "Describe someone facing a choice between a few possible approaches, and "
            "ask which approach is most appropriate given what the lesson teaches.",
        ),
        (
            "behavior/prediction",
            "Describe a specific situation or short sequence of actions, and ask what "
            "would happen as a result and why, based on the lesson content.",
        ),
        (
            "implementation/concept",
            "Ask the learner to choose the implementation or approach that correctly "
            "applies a concept taught in the lesson content.",
        ),
        (
            "conceptual comparison",
            "Ask the learner to distinguish between two closely related concepts from "
            "the lesson content — only use this style if the lesson content actually "
            "contrasts two related ideas.",
        ),
        (
            "troubleshooting/misconception",
            "Describe a plausible mistake someone makes when applying a concept from "
            "the lesson content, and ask what should change, or why the resulting "
            "behavior occurs.",
        ),
        (
            "code-based reasoning",
            "If the lesson content includes code or a technical procedure, use a "
            "short, relevant code snippet or pseudo-code and ask what it does, what "
            "is wrong with it, or how to fix it. If the lesson content has no code, "
            "use a non-code scenario instead.",
        ),
    ]

    _DIFFICULTY_GUIDANCE = {
        "easy": (
            "Test basic understanding or a straightforward, single-step application "
            "of one concept from the lesson content."
        ),
        "medium": (
            "Require applying the concept to a realistic situation, or distinguishing "
            "it from one plausible alternative — more than simple recall."
        ),
        "hard": (
            "Require multi-step reasoning, troubleshooting, or choosing the best of "
            "several plausible implementations or approaches."
        ),
    }

    def _build_prompt(self, segment: str, difficulty: str, blooms: str) -> str:
        # Model-agnostic prompt: no assumptions about a specific model's
        # tokenizer or output quirks — this must work the same way whether
        # LLM_MODEL is qwen2.5:7b or any other Ollama model configured via
        # .env. Targets professional course-assessment quality (understand
        # + apply, not transcript recall or "what is this video about").
        style_name, style_instruction = random.choice(self._QUESTION_STYLES)
        difficulty_guidance = self._DIFFICULTY_GUIDANCE.get(
            difficulty, self._DIFFICULTY_GUIDANCE["medium"]
        )
        return (
            f"You are an instructional designer writing ONE multiple-choice "
            f"assessment question for a professional online technical course (in "
            f"the style of a Coursera course quiz), based on the LESSON CONTENT "
            f"below.\n\n"
            f"The question must test whether a learner can UNDERSTAND and APPLY a "
            f"concept taught in the lesson content — never a question that could be "
            f"answered by only skimming or recalling a definition.\n\n"
            f"Question style for this item ({style_name}): {style_instruction}\n\n"
            f"Difficulty ({difficulty}): {difficulty_guidance}\n\n"
            f"Hard requirements:\n"
            f"- Do NOT say \"the transcript\", \"the video\", or \"the lesson\" in "
            f"the question text — write it exactly like a real course-assessment "
            f"question: describe a situation, a piece of code, or a task directly, "
            f"the way a textbook or course quiz would.\n"
            f"- Do NOT ask what the material is about, its title, or for a summary.\n"
            f"- Do NOT write a simple \"what does X do\" or \"which X was mentioned\" "
            f"recall question — answering correctly must require reasoning about a "
            f"situation, not memorizing a definition.\n"
            f"- Base the question ONLY on concepts actually taught in the LESSON "
            f"CONTENT below — never introduce outside knowledge or invent concepts "
            f"the lesson content doesn't cover, even to make the question harder.\n"
            f"- Prefer concrete application, behavior-prediction, troubleshooting, or "
            f"implementation questions over generic definition questions.\n"
            f"- Do not test unrelated general programming knowledge that the lesson "
            f"content does not cover.\n"
            f"- If you include code, keep it short and directly tied to the concept "
            f"being taught.\n\n"
            f"Technical correctness and grounding (critical):\n"
            f"- Every part of your output — the question, the correct answer, all "
            f"distractors, and the explanation — must be fully supported by the "
            f"LESSON CONTENT below. Do not rely on your own outside knowledge to "
            f"fill in anything the content doesn't actually say.\n"
            f"- Do not invent React/JavaScript behavior, APIs, syntax, rules, or code "
            f"patterns that are not demonstrated or explained in the LESSON CONTENT, "
            f"even if they are true in general — if it isn't in the content, don't "
            f"use it.\n"
            f"- If you write code, the code and its described/expected behavior must "
            f"be technically consistent with each other.\n"
            f"- Do not change or contradict what the lesson content actually teaches "
            f"when constructing the scenario.\n"
            f"- If the LESSON CONTENT below does not contain enough information to "
            f"make a technically certain question, do NOT invent the missing "
            f"information — instead, generate a different question that is fully "
            f"supported by the content.\n\n"
            f"Before you respond, internally verify all of the following, and only "
            f"output a question that passes every check:\n"
            f"1. Exactly one option is correct.\n"
            f"2. The correct option is actually correct for the situation or code "
            f"described, based on the LESSON CONTENT.\n"
            f"3. The explanation agrees with the correct option.\n"
            f"4. Every distractor is plausible but actually incorrect.\n"
            f"5. The question can be answered using the LESSON CONTENT alone.\n\n"
            f"Write exactly 4 answer options, all different from each other. The 3 "
            f"incorrect options must be realistic mistakes or common misconceptions a "
            f"learner could plausibly make — not random, unrelated, or obviously "
            f"absurd choices — so the question requires real reasoning rather than "
            f"trivial elimination.\n\n"
            f"Respond with ONLY a JSON object, no other text, in exactly this shape:\n"
            f'{{"question": "...", "options": ["...", "...", "...", "..."], '
            f'"correct_index": 0, "explanation": "..."}}\n\n'
            f"- \"correct_index\" is the 0-based position (0, 1, 2, or 3) of the one "
            f"correct option.\n"
            f"- \"explanation\" must be a non-empty sentence explaining why that "
            f"option is correct.\n\n"
            f"LESSON CONTENT:\n{segment}"
        )

    # ── Parsing ──────────────────────────────────────────────────────────

    def _parse_generated_question(self, text: str) -> Optional[dict]:
        """Parse provider output into {question, options, correct_index,
        explanation} and validate it. Tries JSON first (preferred — see
        `json_mode=True` above), then falls back to a labeled-text parser
        for models that don't reliably follow the JSON instruction.
        Validation is identical either way, so it stays independent of
        which model produced the output.
        """
        parsed = self._parse_as_json(text) or self._parse_as_labeled_text(text)
        if parsed is None:
            return None
        return self._validate_and_normalize(parsed)

    def _parse_as_json(self, text: str) -> Optional[dict]:
        candidate = text.strip()
        # Some models wrap JSON in prose or markdown fences despite
        # instructions — fall back to extracting the first {...} block.
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    # Accepts "A)", "(A)", and "[A]" option-letter formats.
    _OPTION_LINE_RE = re.compile(r"^\(?\[?([A-D])[\)\]]\s*", re.IGNORECASE)

    def _parse_as_labeled_text(self, text: str) -> Optional[dict]:
        lines = text.strip().split("\n")
        question = ""
        options: list[str] = []
        correct_letters: list[str] = []
        explanation = ""

        for line in lines:
            line = line.strip()
            if line.lower().startswith("question:"):
                question = line.split(":", 1)[1].strip()
                continue
            if line.lower().startswith("correct:"):
                correct_letters = re.findall(r"[A-D]", line.split(":", 1)[1].upper())
                continue
            if line.lower().startswith("explanation:"):
                explanation = line.split(":", 1)[1].strip()
                continue
            option_match = self._OPTION_LINE_RE.match(line)
            if option_match:
                options.append(line[option_match.end():].strip())

        if not question or not options:
            return None
        # Multiple letters after "Correct:" means the model claimed more
        # than one right answer — reject rather than guessing which one.
        correct_index = (
            {"A": 0, "B": 1, "C": 2, "D": 3}[correct_letters[0]]
            if len(correct_letters) == 1
            else -1
        )
        return {
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "explanation": explanation,
        }

    def _validate_and_normalize(self, parsed: dict) -> Optional[dict]:
        """Enforce the full validation checklist. No padding, no
        leniency — if the model didn't produce exactly 4 genuinely
        distinct options with exactly one correct answer and a real
        explanation, the question is rejected (None), not patched.
        """
        question = str(parsed.get("question", "")).strip()
        if not question or len(question) < 12:
            return None

        raw_options = parsed.get("options")
        if not isinstance(raw_options, list) or len(raw_options) != 4:
            return None
        options = [str(o).strip() for o in raw_options]
        if any(not o for o in options):
            return None

        # Genuinely distinct: case/whitespace-insensitive comparison so a
        # model repeating an option with different casing/spacing doesn't
        # slip through as if it were a distinct choice.
        normalized = [re.sub(r"\s+", " ", o.casefold()) for o in options]
        if len(set(normalized)) != 4:
            return None

        correct_index = parsed.get("correct_index")
        try:
            correct_index = int(correct_index)
        except (TypeError, ValueError):
            return None
        if not 0 <= correct_index <= 3:
            return None

        explanation = str(parsed.get("explanation", "")).strip()
        if not explanation:
            return None

        return {
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "explanation": explanation,
        }

    # ── Transcript grounding / genericness ─────────────────────────────

    # Patterns that indicate the model gave up on real assessment-style
    # questions and fell back to a generic, content-free template, or broke
    # the "never say transcript/video/lesson" instruction in a way that
    # signals a trivial recall question rather than a scenario/application
    # one (spec's explicit BAD examples: "main focus of this lesson",
    # "mentioned in the transcript", "according to the transcript...").
    _GENERIC_QUESTION_RE = re.compile(
        r"\b(best|good)\s+title\b"
        r"|\bwhat\s+is\s+(this|the)\s+(video|lesson|module|section)\s+(about|called)\b"
        r"|\bmain\s+(topic|idea|focus|point|purpose)\s+of\s+(this|the)\s+"
        r"(video|lesson|module|section|material)\b"
        r"|\bwhat\s+(did|does)\s+(this|the)\s+(video|lesson|module|section)\s+(cover|discuss|teach)\b"
        r"|\bsummary\s+of\s+(this|the)\s+(video|lesson|module|section)\b"
        r"|\bmentioned\s+in\s+(the\s+)?(transcript|video|lesson)\b"
        r"|\baccording\s+to\s+(the\s+)?(transcript|video|lesson)\b"
        r"|\b(this|the)\s+(transcript|video)\b",
        re.IGNORECASE,
    )
    # Words too short/common — or too generic to *any* scenario-style
    # question, regardless of subject — to count as evidence a question is
    # actually grounded in the segment's specific content.
    _STOPWORDS = {
        "about", "after", "again", "before", "being", "could", "every",
        "first", "should", "their", "there", "these", "thing", "think",
        "those", "using", "which", "while", "would", "video", "student",
        "watched", "answer", "option", "options", "question", "correct",
        "lesson", "situation", "approach", "developer", "concept",
        "consider", "example", "implementation", "realistic", "mistake",
        "choose", "learner", "scenario", "following", "several", "plausible",
    }

    def _content_words(self, text: str) -> set[str]:
        return {
            w for w in re.findall(r"[a-zA-Z]{5,}", text.lower())
            if w not in self._STOPWORDS
        }

    def _is_grounded_in_segment(self, parsed: dict, segment: str) -> bool:
        """Reject questions that are structurally valid but not actually
        about this segment's content (the "best title for this video"
        failure mode) — a cheap, no-extra-LLM-call relevance check that
        stays independent of which model produced the output.
        """
        question_text = str(parsed.get("question", ""))
        if self._GENERIC_QUESTION_RE.search(question_text):
            return False

        segment_words = self._content_words(segment)
        if len(segment_words) < 5:
            # Too little real content in this segment to check against
            # (e.g. a short trailing chunk) — don't penalize for that.
            return True

        answer_text = question_text + " " + " ".join(parsed.get("options", []))
        return bool(segment_words & self._content_words(answer_text))

    def _question_key(self, question_text: str) -> str:
        return re.sub(r"\s+", " ", question_text.strip().casefold())


# ── Singleton ──
question_generator = QuestionGenerator()