"""Progress callback implementations.

Two concrete implementations are provided:
  * :class:`ConsoleProgressCallback` — prints a progress bar to stdout.
    Used by the CLIs (``ingest.py``, ``ingest_catalog.py``).
  * :class:`LoggingProgressCallback` — emits structured log lines.
    Used by unit tests and as the default when no callback is supplied.

A :class:`CompositeProgressCallback` that fans out to multiple
callbacks is also provided for callers that need both console and log
output.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from interfaces.progress_callback import IProgressCallback

logger = logging.getLogger(__name__)


class ConsoleProgressCallback(IProgressCallback):
    """Prints a progress bar to stdout.  Used by the CLIs."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    async def on_stage_start(self, stage, message, total_items=None):
        if self.verbose:
            print(f"\n[STAGE START] {stage}: {message}")
            if total_items:
                print(f"  Total items: {total_items}")

    async def on_progress(self, stage, current, total, message, metadata=None):
        if not self.verbose:
            return
        pct = (current / total * 100) if total > 0 else 0
        bar_length = 30
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "\u2588" * filled + "\u2591" * (bar_length - filled)
        print(
            f"\r  [{bar}] {current}/{total} ({pct:.1f}%) - {message}",
            end="",
            flush=True,
        )
        if current >= total:
            print()

    async def on_stage_complete(self, stage, message, result=None):
        if self.verbose:
            print(f"\n[STAGE COMPLETE] {stage}: {message}")

    async def on_error(self, stage, error, page_number=None):
        prefix = (
            f"[ERROR] Page {page_number} - " if page_number is not None else "[ERROR] "
        )
        print(f"\n{prefix}{stage}: {error}")


class LoggingProgressCallback(IProgressCallback):
    """Emits structured log lines.  Used by unit tests and as the default."""

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    async def on_stage_start(self, stage, message, total_items=None):
        logger.log(self.log_level, f"[Pipeline] Stage '{stage}' started: {message}")

    async def on_progress(self, stage, current, total, message, metadata=None):
        pct = (current / total * 100) if total > 0 else 0
        logger.log(
            self.log_level,
            f"[Pipeline] {stage}: {current}/{total} ({pct:.1f}%) - {message}",
        )

    async def on_stage_complete(self, stage, message, result=None):
        logger.log(self.log_level, f"[Pipeline] Stage '{stage}' completed: {message}")

    async def on_error(self, stage, error, page_number=None):
        context = f" (page {page_number})" if page_number is not None else ""
        logger.error(f"[Pipeline] Error in '{stage}'{context}: {error}", exc_info=True)


class CompositeProgressCallback(IProgressCallback):
    """Fans out to multiple callbacks.  Swallows per-callback exceptions."""

    def __init__(self, callbacks: list):
        self.callbacks = callbacks

    async def on_stage_start(self, stage, message, total_items=None):
        for cb in self.callbacks:
            try:
                await cb.on_stage_start(stage, message, total_items)
            except Exception:
                logger.exception("progress callback on_stage_start failed")

    async def on_progress(self, stage, current, total, message, metadata=None):
        for cb in self.callbacks:
            try:
                await cb.on_progress(stage, current, total, message, metadata)
            except Exception:
                logger.exception("progress callback on_progress failed")

    async def on_stage_complete(self, stage, message, result=None):
        for cb in self.callbacks:
            try:
                await cb.on_stage_complete(stage, message, result)
            except Exception:
                logger.exception("progress callback on_stage_complete failed")

    async def on_error(self, stage, error, page_number=None):
        for cb in self.callbacks:
            try:
                await cb.on_error(stage, error, page_number)
            except Exception:
                logger.exception("progress callback on_error failed")
