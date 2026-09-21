"""
scraping — Auto Content Discovery Module for NeuroLearn

Exposes:
    discover_content(topic, max_videos) -> dict
    scrape_youtube(topic, max_results)  -> list[ScrapedVideo]
"""

from .pipeline import discover_content
from .youtube_scraper import scrape_youtube, ScrapedVideo

__all__ = ["discover_content", "scrape_youtube", "ScrapedVideo"]
