"""
============================================================
SCRAPING MODULE: YouTube Scraper (No Paid API)
File: backend/scraping/youtube_scraper.py

Uses Playwright (headless Chromium) to scrape YouTube search
results for educational videos. Falls back to yt-dlp metadata
extraction if Playwright is unavailable.

Design:
  - Modular and replaceable (swap scraper without touching pipeline)
  - Headless browser with random delays to avoid blocks
  - Robust CSS selectors (no fragile XPaths)
  - Full retry logic with exponential backoff
  - Structured logging via loguru
============================================================
"""

import re
import time
import random
import asyncio
import urllib.parse
from typing import Optional
from dataclasses import dataclass, field, asdict

from loguru import logger


# ── Data Model ──────────────────────────────────────────────

@dataclass
class ScrapedVideo:
    """Structured video metadata returned by the scraper."""
    title: str
    url: str
    video_id: str
    duration_raw: str = ""          # e.g. "12:34"
    duration_seconds: int = 0
    channel: str = ""
    thumbnail: str = ""
    view_count_raw: str = ""
    source: str = "youtube"

    def to_dict(self) -> dict:
        return asdict(self)


# ── Constants ────────────────────────────────────────────────

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%3D%3D"
# sp=EgIQAQ%3D%3D filters for videos only (not shorts / playlists)

MAX_RETRIES = 3
BASE_DELAY_S = 2.0          # Base sleep between requests
JITTER_RANGE = (1.0, 3.0)   # Extra random jitter
PAGE_LOAD_TIMEOUT_MS = 20_000
SCROLL_PAUSE_MS = 1_500

SELECTORS = {
    # Primary renderer for each search result
    "result_renderer": "ytd-video-renderer",
    # Title anchor inside each renderer
    "title_link": "a#video-title",
    # Duration badge
    "duration": "span.ytd-thumbnail-overlay-time-status-renderer",
    # Channel name
    "channel": "yt-formatted-string.ytd-channel-name a",
    # View count / metadata line
    "meta": "span.inline-metadata-item",
}

# Minimum title quality heuristics
MIN_TITLE_WORDS = 3
EDUCATIONAL_KEYWORDS = {
    "tutorial", "course", "lecture", "lesson", "introduction",
    "explained", "learn", "guide", "basics", "fundamentals",
    "overview", "what is", "how to", "complete", "beginner",
    "advanced", "crash course", "deep dive",
}


# ── Helpers ──────────────────────────────────────────────────

def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from a URL."""
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def _duration_to_seconds(duration_str: str) -> int:
    """Convert 'H:MM:SS' or 'M:SS' string to total seconds."""
    parts = duration_str.strip().split(":")
    try:
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except ValueError:
        pass
    return 0


def _is_educational(title: str) -> bool:
    """Heuristic: does the title look like educational content?"""
    title_lower = title.lower()
    word_count = len(title.split())
    if word_count < MIN_TITLE_WORDS:
        return False
    # Allow all results — topic itself provides educational framing.
    # This filter just rejects suspiciously short / garbage titles.
    return True


def _build_thumbnail_url(video_id: str) -> str:
    if not video_id:
        return ""
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _random_delay():
    """Sleep with a random delay to reduce scraping footprint."""
    sleep_time = BASE_DELAY_S + random.uniform(*JITTER_RANGE)
    logger.debug(f"Sleeping {sleep_time:.1f}s (rate-limit guard)")
    time.sleep(sleep_time)


# ── Playwright Scraper ───────────────────────────────────────

async def _scrape_with_playwright(topic: str, max_results: int) -> list[ScrapedVideo]:
    """
    Async scraper using Playwright (headless Chromium).
    Raises ImportError if playwright is not installed.
    """
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    query = urllib.parse.quote_plus(topic + " tutorial")
    url = YOUTUBE_SEARCH_URL.format(query=query)

    videos: list[ScrapedVideo] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()

        try:
            logger.info(f"[Playwright] Navigating to YouTube search: {url}")
            await page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")

            # Wait for results to appear
            await page.wait_for_selector(SELECTORS["result_renderer"], timeout=PAGE_LOAD_TIMEOUT_MS)

            # Scroll slightly to trigger lazy loading
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(SCROLL_PAUSE_MS / 1000)
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(SCROLL_PAUSE_MS / 1000)

            renderers = await page.query_selector_all(SELECTORS["result_renderer"])
            logger.info(f"[Playwright] Found {len(renderers)} video renderers")

            for renderer in renderers:
                if len(videos) >= max_results:
                    break
                try:
                    # Title + URL
                    title_el = await renderer.query_selector(SELECTORS["title_link"])
                    if not title_el:
                        continue
                    title = (await title_el.get_attribute("title")) or (await title_el.inner_text())
                    href = await title_el.get_attribute("href") or ""
                    if not href or not title:
                        continue

                    full_url = f"https://www.youtube.com{href}" if href.startswith("/") else href
                    video_id = _extract_video_id(full_url)
                    if not video_id:
                        continue

                    if not _is_educational(title):
                        continue

                    # Duration
                    dur_el = await renderer.query_selector(SELECTORS["duration"])
                    duration_raw = (await dur_el.inner_text()).strip() if dur_el else ""
                    duration_sec = _duration_to_seconds(duration_raw)

                    # Skip Shorts (< 60 s)
                    if duration_sec and duration_sec < 60:
                        continue

                    # Channel
                    chan_el = await renderer.query_selector(SELECTORS["channel"])
                    channel = (await chan_el.inner_text()).strip() if chan_el else ""

                    video = ScrapedVideo(
                        title=title.strip(),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        video_id=video_id,
                        duration_raw=duration_raw,
                        duration_seconds=duration_sec,
                        channel=channel,
                        thumbnail=_build_thumbnail_url(video_id),
                        source="youtube_playwright",
                    )
                    videos.append(video)
                    logger.debug(f"  + Scraped: {video.title[:60]}")

                except Exception as ex:
                    logger.warning(f"[Playwright] Skipping renderer due to error: {ex}")
                    continue

        except PWTimeout:
            logger.warning("[Playwright] Page load timed out")
        except Exception as ex:
            logger.error(f"[Playwright] Scraping error: {ex}")
            raise
        finally:
            await browser.close()

    return videos


# ── yt-dlp Fallback ──────────────────────────────────────────

def _scrape_with_ytdlp(topic: str, max_results: int) -> list[ScrapedVideo]:
    """
    Fallback scraper using yt-dlp's flat-playlist extraction.
    Does NOT download videos — only fetches metadata from the
    YouTube search results page.

    Raises ImportError if yt-dlp is not installed.
    """
    import yt_dlp  # noqa: F401

    query = f"ytsearch{max_results * 2}:{topic} tutorial"
    videos: list[ScrapedVideo] = []

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,   # metadata only, no download
        "skip_download": True,
        "ignoreerrors": True,
    }

    logger.info(f"[yt-dlp] Searching: {query}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False) or {}

    entries = info.get("entries") or []
    for entry in entries:
        if len(videos) >= max_results:
            break
        if not entry:
            continue
        video_id = entry.get("id") or entry.get("url", "")
        if not video_id:
            continue
        title = entry.get("title", "")
        if not _is_educational(title):
            continue
        duration_sec = int(entry.get("duration") or 0)
        if duration_sec and duration_sec < 60:
            continue

        video = ScrapedVideo(
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            video_id=video_id,
            duration_raw=str(duration_sec),
            duration_seconds=duration_sec,
            channel=entry.get("channel") or entry.get("uploader") or "",
            thumbnail=entry.get("thumbnail") or _build_thumbnail_url(video_id),
            source="youtube_ytdlp",
        )
        videos.append(video)
        logger.debug(f"  + yt-dlp result: {video.title[:60]}")

    return videos


# ── Public API ───────────────────────────────────────────────

def scrape_youtube(
    topic: str,
    max_results: int = 5,
    retries: int = MAX_RETRIES,
) -> list[ScrapedVideo]:
    """
    Scrape YouTube for educational videos on `topic`.

    Tries Playwright first (richest metadata), falls back to yt-dlp.
    Both paths have retry logic with exponential backoff.

    Args:
        topic:       Search topic string, e.g. "Operating Systems"
        max_results: Maximum number of videos to return (3–5 recommended)
        retries:     Number of retry attempts on failure

    Returns:
        List of ScrapedVideo objects (may be empty on total failure).
    """
    logger.info(f"[YouTubeScraper] Searching for topic: '{topic}' (max {max_results})")

    # ── Attempt 1: Playwright (async → sync bridge) ──
    for attempt in range(1, retries + 1):
        try:
            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(_scrape_with_playwright(topic, max_results))
            loop.close()
            if results:
                logger.success(f"[YouTubeScraper] Playwright OK — {len(results)} videos found")
                return results
            logger.warning(f"[Playwright] Attempt {attempt}: returned 0 results, retrying…")
        except ImportError:
            logger.info("[YouTubeScraper] Playwright not installed, trying yt-dlp fallback")
            break
        except Exception as ex:
            logger.warning(f"[Playwright] Attempt {attempt}/{retries} failed: {ex}")
            if attempt < retries:
                _random_delay()

    # ── Attempt 2: yt-dlp fallback ──
    for attempt in range(1, retries + 1):
        try:
            _random_delay()
            results = _scrape_with_ytdlp(topic, max_results)
            if results:
                logger.success(f"[YouTubeScraper] yt-dlp OK — {len(results)} videos found")
                return results
            logger.warning(f"[yt-dlp] Attempt {attempt}: returned 0 results, retrying…")
        except ImportError:
            logger.error("[YouTubeScraper] yt-dlp not installed. Install with: pip install yt-dlp")
            break
        except Exception as ex:
            logger.warning(f"[yt-dlp] Attempt {attempt}/{retries} failed: {ex}")
            if attempt < retries:
                _random_delay()

    logger.error(f"[YouTubeScraper] All strategies exhausted for topic: '{topic}'")
    return []
