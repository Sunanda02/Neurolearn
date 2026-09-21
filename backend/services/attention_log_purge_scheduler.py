"""Scheduled purge job for expired attention logs."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress

from loguru import logger

from data.database import purge_expired_attention_logs


DEFAULT_PURGE_INTERVAL_SECONDS = 24 * 60 * 60


def _purge_interval_seconds() -> int:
    raw = os.getenv("ATTENTION_LOG_PURGE_INTERVAL_SECONDS")
    if raw is None:
        return DEFAULT_PURGE_INTERVAL_SECONDS
    try:
        return max(60, int(raw))
    except ValueError:
        logger.warning(
            "Invalid ATTENTION_LOG_PURGE_INTERVAL_SECONDS={!r}; using {} seconds",
            raw,
            DEFAULT_PURGE_INTERVAL_SECONDS,
        )
        return DEFAULT_PURGE_INTERVAL_SECONDS


async def _run_purge_once() -> int:
    return await asyncio.to_thread(purge_expired_attention_logs)


async def attention_log_purge_loop(stop_event: asyncio.Event) -> None:
    """
    Purge expired attention logs at startup, then periodically.

    Expiration itself stays centralized in purge_expired_attention_logs():
    a row older than the student's consent retention window, default 30 days,
    is deleted from PostgreSQL.
    """
    interval_seconds = _purge_interval_seconds()
    logger.info(
        "Scheduled expired-attention-log purge every {} seconds",
        interval_seconds,
    )

    while not stop_event.is_set():
        try:
            removed = await _run_purge_once()
            logger.info("Expired-attention-log purge completed; removed={} rows", removed)
        except Exception:
            logger.exception("Expired-attention-log purge failed")

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)


async def stop_attention_log_purge(
    task: asyncio.Task | None,
    stop_event: asyncio.Event | None,
) -> None:
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
