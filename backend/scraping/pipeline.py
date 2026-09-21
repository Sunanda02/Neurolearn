"""
============================================================
SCRAPING MODULE: Content Discovery Pipeline
File: backend/scraping/pipeline.py

Orchestrates the full auto-course generation flow:
  1. Accept topic input
  2. Invoke YouTube scraper
  3. Clean, deduplicate, rank results
  4. Return structured video list ready for DB insertion
  5. (Optionally) trigger downstream transcription + assessment

Designed as a modular, replaceable component — the scraper
implementation can be swapped without touching this file.
============================================================
"""

import re
import uuid
import time
from typing import Optional
from loguru import logger

from scraping.youtube_scraper import scrape_youtube, ScrapedVideo


# ── Config ───────────────────────────────────────────────────

DEFAULT_MAX_VIDEOS = 5
MIN_VIDEOS_THRESHOLD = 1      # Minimum acceptable results before warning

# FIX (course generator request): the pipeline used to issue exactly ONE
# search — "{topic} tutorial" — and take the top `max_videos * 2` results
# from it. For any broad topic, the videos that rank highest for a single
# generic "X tutorial" query are overwhelmingly beginner/overview content
# ("X Tutorial for Beginners", "X Crash Course", "X in 30 Minutes", "X
# Full Course") from different channels — so every "course" ended up as
# 5 different videos covering the same introductory ground, never
# reaching intermediate or advanced material. That's exactly the
# "similar content, all the beginning of the course" bug.
#
# The fix: issue one search PER curriculum stage, with a query modifier
# that actually steers YouTube/yt-dlp's own ranking toward that stage's
# level (e.g. "React advanced patterns performance" surfaces different
# videos than "React introduction fundamentals" — these are genuinely
# different searches, not a re-sort of one pool). Stages are listed in
# teaching order; video `order` fields follow this order so the course
# has real progression instead of N interchangeable intros.
CURRICULUM_STAGES = [
    # (stage_id, label, query_modifier, title-scoring hint keywords)
    ("fundamentals", "Fundamentals", "introduction fundamentals basics for beginners",
     {"introduction", "intro", "basics", "beginner", "fundamentals", "getting started", "what is"}),
    ("core_concepts", "Core Concepts", "core concepts explained tutorial",
     {"concepts", "explained", "how", "guide", "deep dive"}),
    ("intermediate", "Intermediate Techniques", "intermediate tutorial techniques",
     {"intermediate", "techniques", "patterns", "practical"}),
    ("advanced", "Advanced Topics", "advanced techniques best practices",
     {"advanced", "best practices", "optimization", "performance", "architecture"}),
    ("applied_project", "Applied Project", "practical project tutorial real world",
     {"project", "build", "real world", "practical", "walkthrough", "case study"}),
]

_STOPWORDS = {
    "a", "an", "the", "to", "for", "of", "in", "on", "with", "and", "or",
    "your", "you", "is", "are", "how", "what", "this", "that", "full",
    "course", "tutorial", "video", "part", "2023", "2024", "2025", "2026",
}


def _title_tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _is_near_duplicate(candidate_tokens: set[str], chosen_token_sets: list[set[str]], threshold: float = 0.6) -> bool:
    """
    Jaccard similarity check across ALL already-selected videos, not just
    within the current stage — this is what stops two different stages
    from both independently picking an "Introduction to X" video under
    slightly different titles (the old code's dedup only compared the
    first 40 characters of title strings within one flat list, which
    caught exact near-duplicates but not two differently-worded intro
    videos selected from two different searches).
    """
    if not candidate_tokens:
        return False
    for chosen in chosen_token_sets:
        if not chosen:
            continue
        overlap = len(candidate_tokens & chosen)
        union = len(candidate_tokens | chosen)
        if union and (overlap / union) >= threshold:
            return True
    return False


# ── Cleaning Helpers ─────────────────────────────────────────

_NOISE_PATTERNS = [
    re.compile(r"\s*\|\s*.*$"),          # Remove "| Channel Name" suffixes
    re.compile(r"\s*-\s*youtube\s*$", re.I),
    re.compile(r"\s*\(official.*?\)", re.I),
    re.compile(r"\s*\[.*?\]"),           # Remove [brackets]
    re.compile(r"\s{2,}"),              # Collapse extra whitespace
]


def _clean_title(title: str) -> str:
    """Strip noisy suffixes / brackets from video titles."""
    cleaned = title
    for pattern in _NOISE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return cleaned.strip()


def _deduplicate(videos: list[ScrapedVideo]) -> list[ScrapedVideo]:
    """
    Remove duplicate videos by video_id.
    Also removes near-duplicate titles (same first 40 chars).
    """
    seen_ids: set[str] = set()
    seen_title_prefixes: set[str] = set()
    unique: list[ScrapedVideo] = []

    for video in videos:
        if video.video_id in seen_ids:
            continue
        title_prefix = video.title[:40].lower().strip()
        if title_prefix in seen_title_prefixes:
            continue
        seen_ids.add(video.video_id)
        seen_title_prefixes.add(title_prefix)
        unique.append(video)

    return unique


def _rank_videos(videos: list[ScrapedVideo], topic: str, stage_hint_keywords: Optional[set[str]] = None) -> list[ScrapedVideo]:
    """
    Heuristic ranking — prefer videos that:
      - Mention the topic in the title
      - Have a reasonable duration (5 min – 2 hr)
      - Come from recognisable educational channels
      - FIX (course generator request): match the requested curriculum
        stage's level (stage_hint_keywords) — this is what makes an
        "advanced" search actually prefer advanced-reading titles over
        yet another beginner overview that happened to rank for the
        broader query, instead of ranking purely on topic overlap.
    Returns sorted list (best first).
    """
    topic_words = set(topic.lower().split())

    EDUCATIONAL_CHANNELS = {
        "mit opencourseware", "stanford", "khan academy", "freeCodeCamp",
        "traversy media", "fireship", "sentdex", "3blue1brown", "numberphile",
        "computerphile", "tech with tim", "corey schafer", "programming with mosh",
        "the coding train", "crash course", "neso academy", "gate smashers",
        "jenny's lectures", "abdul bari",
    }

    def _score(v: ScrapedVideo) -> float:
        score = 0.0
        title_lower = v.title.lower()

        # Topic keyword overlap
        matched_words = sum(1 for w in topic_words if w in title_lower)
        score += matched_words * 2.0

        # Duration sweet spot: 5 min–2 hr
        if 300 <= v.duration_seconds <= 7200:
            score += 1.5
        elif v.duration_seconds > 0:
            score += 0.5

        # Educational channel bonus
        chan_lower = v.channel.lower()
        if any(ec in chan_lower for ec in EDUCATIONAL_CHANNELS):
            score += 2.0

        # Prefer results that have a valid thumbnail
        if v.thumbnail:
            score += 0.5

        # Stage-level match: reward titles that read as the level we're
        # searching for. Without this, "advanced" and "fundamentals"
        # searches score identically and just fall back to topic overlap
        # + channel reputation — which is exactly how every stage ended
        # up picking the same handful of generic overview videos.
        if stage_hint_keywords:
            if any(kw in title_lower for kw in stage_hint_keywords):
                score += 3.0

        return score

    return sorted(videos, key=_score, reverse=True)


# ── Video → API Structure ─────────────────────────────────────

def _video_to_api_dict(video: ScrapedVideo, order: int, topic: str, stage_label: str = "") -> dict:
    """
    Convert a ScrapedVideo into the VideoLink-compatible dict
    used by the existing NeuroLearn Course schema.
    """
    video_db_id = f"auto_{video.video_id}"
    return {
        "id": video_db_id,
        "title": _clean_title(video.title),
        "url": video.url,
        "duration": video.duration_seconds or 600,   # default 10 min if unknown
        "thumbnail": video.thumbnail,
        "order": order,
        "completed": False,
        "watched_percent": 0.0,
        "channel": video.channel,
        "source": video.source,
        "assessment_available": True,       # Pipeline will generate one
        "transcription_available": False,   # Set True after Whisper processes it
        "scraped_for_topic": topic,
        # FIX (course generator request): which curriculum stage this
        # video was selected for (Fundamentals / Core Concepts /
        # Intermediate / Advanced / Applied Project) — lets the frontend
        # show real progression instead of an unlabeled flat list, and
        # makes it possible to audit that a course actually spans levels.
        "stage_label": stage_label,
    }


# ── Public Pipeline Function ──────────────────────────────────

def discover_content(
    topic: str,
    max_videos: int = DEFAULT_MAX_VIDEOS,
) -> dict:
    """
    Main entry point for the auto-course generation pipeline.

    FIX (course generator request): previously issued exactly one search
    — scrape_youtube(f"{topic} tutorial") — and took the top
    `max_videos * 2` results from that single pool. For a broad topic,
    that pool is dominated by beginner/overview videos (that's what
    ranks highest for a generic "X tutorial" query on YouTube), so every
    generated "course" ended up as several differently-titled but
    content-overlapping intro videos — never reaching intermediate or
    advanced material. This function now issues one search PER
    curriculum stage (see CURRICULUM_STAGES) with a stage-specific query
    modifier, so the underlying searches are genuinely different, and
    ranks each stage's candidates with a stage-aware score that prefers
    titles actually matching that level. A cross-stage similarity check
    (_is_near_duplicate) stops two stages from both picking
    differently-worded versions of the same intro video.

    Args:
        topic:      Educational topic, e.g. "Operating Systems"
        max_videos: How many videos to include (3–5 recommended)

    Returns:
        {
            "course_id": "auto_<uuid>",
            "course_title": "Operating Systems",
            "topic": "Operating Systems",
            "videos": [ { VideoLink dict, now with "stage_label" }, ... ],
            "total_found": int,
            "stages_covered": [str, ...],   # NEW: which curriculum stages actually got a video
            "generated_at": float (unix timestamp),
            "status": "success" | "partial" | "failed",
        }
    """
    logger.info(f"[Pipeline] Starting content discovery for topic: '{topic}' (curriculum-stage mode)")
    start_time = time.time()

    # Decide how many stages to use and how many videos per stage.
    # Fewer requested videos than stages → use the first N stages
    # (fundamentals-first) rather than skipping around, since a partial
    # course should still start from the beginning. More videos than
    # stages → extra videos go to later (harder) stages first, since
    # those are exactly the ones the old single-query approach starved.
    num_stages = min(len(CURRICULUM_STAGES), max_videos)
    stages = CURRICULUM_STAGES[:num_stages]
    videos_per_stage = {s[0]: 1 for s in stages}
    leftover = max_videos - num_stages
    stage_idx = len(stages) - 1
    while leftover > 0 and stages:
        stage_id = stages[stage_idx % len(stages)][0]
        videos_per_stage[stage_id] += 1
        leftover -= 1
        stage_idx -= 1  # walk backwards from advanced → fundamentals

    chosen_videos: list[tuple[ScrapedVideo, str]] = []  # (video, stage_label)
    chosen_token_sets: list[set[str]] = []
    stages_covered: list[str] = []

    for stage_id, stage_label, query_modifier, hint_keywords in stages:
        want = videos_per_stage[stage_id]
        stage_query = f"{topic} {query_modifier}"
        logger.info(f"[Pipeline] Stage '{stage_label}': searching '{stage_query}' (want {want})")

        raw = scrape_youtube(stage_query, max_results=max(want * 3, 6))
        deduped = _deduplicate(raw)
        ranked = _rank_videos(deduped, topic, stage_hint_keywords=hint_keywords)

        picked_this_stage = 0
        for v in ranked:
            if picked_this_stage >= want:
                break
            tokens = _title_tokens(v.title)
            if _is_near_duplicate(tokens, chosen_token_sets):
                logger.debug(f"  - Skipping near-duplicate of an already-chosen video: {v.title[:60]}")
                continue
            chosen_videos.append((v, stage_label))
            chosen_token_sets.append(tokens)
            picked_this_stage += 1

        if picked_this_stage > 0:
            stages_covered.append(stage_label)
        else:
            logger.warning(f"[Pipeline] Stage '{stage_label}' produced 0 usable videos")

    # If some stage failed entirely (e.g. scraper down for one query),
    # backfill from the fundamentals stage's leftovers rather than
    # silently shipping a short course — better a slightly
    # intro-weighted course than one video short.
    if len(chosen_videos) < max_videos and stages:
        logger.warning(
            f"[Pipeline] Only {len(chosen_videos)}/{max_videos} videos found across "
            f"{len(stages)} stages — backfilling from fundamentals"
        )
        fallback_query = f"{topic} {stages[0][2]}"
        raw = scrape_youtube(fallback_query, max_results=max_videos * 3)
        ranked = _rank_videos(_deduplicate(raw), topic, stage_hint_keywords=stages[0][3])
        for v in ranked:
            if len(chosen_videos) >= max_videos:
                break
            tokens = _title_tokens(v.title)
            if _is_near_duplicate(tokens, chosen_token_sets):
                continue
            chosen_videos.append((v, stages[0][1]))
            chosen_token_sets.append(tokens)

    # ── Build API-ready structures, in curriculum order ──
    video_dicts = [
        _video_to_api_dict(v, idx + 1, topic, stage_label=label)
        for idx, (v, label) in enumerate(chosen_videos)
    ]

    elapsed = round(time.time() - start_time, 2)
    status = "success" if len(video_dicts) >= MIN_VIDEOS_THRESHOLD else "failed"
    if 0 < len(video_dicts) < max_videos:
        status = "partial"

    logger.info(
        f"[Pipeline] Done in {elapsed}s — status={status}, videos={len(video_dicts)}, "
        f"stages_covered={stages_covered}"
    )

    return {
        "course_id": f"auto_{uuid.uuid4().hex[:10]}",
        "course_title": topic.title(),
        "topic": topic,
        "description": f"Auto-generated course on '{topic.title()}' using web-sourced educational videos, "
                        f"spanning {len(stages_covered)} curriculum stage(s): {', '.join(stages_covered) or 'none'}.",
        "icon": "🎓",
        "category": "Auto-Generated",
        "difficulty": "Intermediate",
        "tags": topic.lower().split() + ["auto-generated"],
        "videos": video_dicts,
        "total_found": len(video_dicts),
        "stages_covered": stages_covered,
        "generated_at": start_time,
        "elapsed_seconds": elapsed,
        "status": status,
    }
