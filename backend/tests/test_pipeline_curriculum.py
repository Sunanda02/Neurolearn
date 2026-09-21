"""
tests/test_pipeline_curriculum.py — verifies the course-generator fix.

Reproduces the exact bug reported: "course generator picks up videos
that have almost similar content which is the beginning of the course,
not the whole course." Mocks scrape_youtube() to behave like real
YouTube search would — a query containing "introduction fundamentals"
returns beginner-titled results, a query containing "advanced
techniques" returns advanced-titled results, etc. — and asserts the
pipeline actually issues distinct per-stage queries and assembles a
course spanning multiple levels, not five variations of "X for
Beginners".
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from scraping.youtube_scraper import ScrapedVideo
from scraping.pipeline import discover_content, CURRICULUM_STAGES, _is_near_duplicate, _title_tokens

# Simulated "YouTube search index" — a realistic pool per query keyword,
# mirroring how real search results skew heavily toward beginner content
# for ANY generic query, but differ when the query is actually specific.
FAKE_RESULTS_BY_KEYWORD = {
    "introduction fundamentals basics for beginners": [
        ScrapedVideo("React JS Full Course for Beginners", "https://youtube.com/watch?v=aaa1", "aaa1", "20:00", 1200, "freeCodeCamp"),
        ScrapedVideo("React Tutorial for Beginners 2024", "https://youtube.com/watch?v=aaa2", "aaa2", "15:00", 900, "Programming with Mosh"),
        ScrapedVideo("Learn React in 30 Minutes", "https://youtube.com/watch?v=aaa3", "aaa3", "30:00", 1800, "Traversy Media"),
    ],
    "core concepts explained tutorial": [
        ScrapedVideo("React Core Concepts Explained", "https://youtube.com/watch?v=bbb1", "bbb1", "25:00", 1500, "Fireship"),
        ScrapedVideo("Understanding React Components Deep Dive", "https://youtube.com/watch?v=bbb2", "bbb2", "18:00", 1080, "Tech With Tim"),
    ],
    "intermediate tutorial techniques": [
        ScrapedVideo("Intermediate React Patterns", "https://youtube.com/watch?v=ccc1", "ccc1", "22:00", 1320, "Corey Schafer"),
    ],
    "advanced techniques best practices": [
        ScrapedVideo("Advanced React Performance Optimization", "https://youtube.com/watch?v=ddd1", "ddd1", "35:00", 2100, "Fireship"),
        ScrapedVideo("React Architecture Best Practices", "https://youtube.com/watch?v=ddd2", "ddd2", "28:00", 1680, "Traversy Media"),
    ],
    "practical project tutorial real world": [
        ScrapedVideo("Build a Real World React Project", "https://youtube.com/watch?v=eee1", "eee1", "45:00", 2700, "freeCodeCamp"),
    ],
}


def fake_scrape_youtube(topic: str, max_results: int = 5, retries: int = 3):
    """Return whichever fake pool matches a keyword substring in `topic`."""
    for keyword, pool in FAKE_RESULTS_BY_KEYWORD.items():
        if keyword in topic:
            return pool[:max_results]
    return []


def test_issues_distinct_queries_per_stage():
    """The old bug: exactly one query ('{topic} tutorial') was ever issued."""
    queries_seen = []

    def spy_scrape(topic, max_results=5, retries=3):
        queries_seen.append(topic)
        return fake_scrape_youtube(topic, max_results, retries)

    with patch("scraping.pipeline.scrape_youtube", side_effect=spy_scrape):
        discover_content("React", max_videos=5)

    assert len(queries_seen) >= len(CURRICULUM_STAGES), (
        f"Expected at least {len(CURRICULUM_STAGES)} distinct stage queries, "
        f"got {len(queries_seen)}: {queries_seen}"
    )
    # Every query must be a DIFFERENT string — proves this isn't one flat
    # search being re-used, which was the entire bug.
    assert len(set(queries_seen)) == len(queries_seen), (
        f"Expected all distinct queries, got duplicates: {queries_seen}"
    )


def test_course_spans_multiple_curriculum_stages():
    """The actual user-facing bug: does the final course contain more
    than just beginner-level videos?"""
    with patch("scraping.pipeline.scrape_youtube", side_effect=fake_scrape_youtube):
        result = discover_content("React", max_videos=5)

    stage_labels = {v["stage_label"] for v in result["videos"]}
    assert len(stage_labels) >= 3, (
        f"Course only spans {stage_labels} — should cover fundamentals "
        f"through advanced, not repeat one level"
    )
    # Specifically: at least one non-beginner stage must be present —
    # this is the literal complaint ("not the whole course").
    assert "Advanced Topics" in stage_labels or "Applied Project" in stage_labels, (
        f"No advanced/applied content made it into the course: {stage_labels}"
    )


def test_cross_stage_near_duplicates_are_rejected():
    """Two stages both surfacing a differently-worded intro video should
    not both make it into the final course."""
    def near_dup_scrape(topic, max_results=5, retries=3):
        # Every stage's search "coincidentally" also returns a
        # near-identical beginner video, worded slightly differently.
        base = fake_scrape_youtube(topic, max_results, retries)
        distractor = ScrapedVideo(
            "React JS Full Course For Beginners (2024 Edition)",
            "https://youtube.com/watch?v=zzz9", "zzz9", "20:00", 1200, "Some Channel",
        )
        return base + [distractor]

    with patch("scraping.pipeline.scrape_youtube", side_effect=near_dup_scrape):
        result = discover_content("React", max_videos=5)

    titles = [v["title"] for v in result["videos"]]
    beginner_like = [t for t in titles if _is_near_duplicate(
        _title_tokens("React JS Full Course for Beginners"), [_title_tokens(t)]
    )]
    assert len(beginner_like) <= 1, f"Near-duplicate beginner videos leaked through: {beginner_like}"


def test_backfill_when_a_stage_returns_nothing():
    """If one stage's search comes back empty, the course should still
    reach max_videos by backfilling, not silently ship short."""
    def flaky_scrape(topic, max_results=5, retries=3):
        if "advanced" in topic:
            return []  # simulate that stage failing entirely
        return fake_scrape_youtube(topic, max_results, retries)

    with patch("scraping.pipeline.scrape_youtube", side_effect=flaky_scrape):
        result = discover_content("React", max_videos=5)

    assert result["total_found"] == 5, (
        f"Expected backfill to reach 5 videos despite one stage failing, got {result['total_found']}"
    )


if __name__ == "__main__":
    test_issues_distinct_queries_per_stage()
    print("PASS: distinct queries per stage")
    test_course_spans_multiple_curriculum_stages()
    print("PASS: course spans multiple curriculum stages")
    test_cross_stage_near_duplicates_are_rejected()
    print("PASS: cross-stage near-duplicates rejected")
    test_backfill_when_a_stage_returns_nothing()
    print("PASS: backfill on stage failure")
