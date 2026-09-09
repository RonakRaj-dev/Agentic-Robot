"""Shared helpers for walking Book documents across the service boundary.

``IBookService.get_book`` is typed as ``-> Any`` because production
(``MongoBookService``) returns a ``Book`` Pydantic model while the
unit-test mock (``InMemoryBookService``) returns a plain ``dict``.
These helpers normalise both shapes so the pipeline (and the object
service) can walk chapters uniformly without sprinkling
``isinstance`` checks at every call site.

The helpers live here (in the pipeline package) rather than in
``utils/`` because they encode a pipeline-specific contract about what
``get_book`` returns — they are NOT general-purpose model utilities.
"""
from __future__ import annotations

from typing import Any, Iterator

from core.exceptions import MongoWriteError


def iter_chapters(book: Any) -> Iterator[dict[str, Any]]:
    """Yield each chapter as a plain dict, regardless of book's type.

    Each yielded dict carries ``id``, ``chapter_no``, and
    ``processed_pages`` — the three fields the pipeline needs to
    decide whether to clear existing page objects and how to compute
    the ``total_pages`` delta.
    """
    if book is None:
        return
    if isinstance(book, dict):
        chapters = book.get("chapters") or []
    else:
        chapters = getattr(book, "chapters", []) or []
    for ch in chapters:
        yield _normalise_chapter(ch)


def find_chapter(book: Any, chapter_no: int) -> dict[str, Any] | None:
    """Return the chapter with the given ``chapter_no``, or None."""
    for ch in iter_chapters(book):
        if ch["chapter_no"] == chapter_no:
            return ch
    return None


def lookup_chapter_for_ingest(
    book: Any, book_id: str, chapter_no: int,
) -> tuple[str, int]:
    """Given a fetched book, extract ``(chapter_id, prev_processed_pages)``.

    Raises ``MongoWriteError`` if the chapter is not found in the book.
    The caller is responsible for fetching the book (so this helper
    doesn't need an ``IBookService`` reference and is pure).
    """
    if book is None:
        raise MongoWriteError(
            f"Book {book_id} not found during chapter PDF upload",
            collection="BOOKS",
        )
    ch = find_chapter(book, chapter_no)
    if ch is None or ch.get("id") is None:
        raise MongoWriteError(
            f"Chapter {chapter_no} not found in book {book_id}",
            collection="BOOKS",
        )
    chapter_id = str(ch["id"])
    previous_processed_pages = int(ch.get("processed_pages") or 0)
    return chapter_id, previous_processed_pages


def _normalise_chapter(ch: Any) -> dict[str, Any]:
    """Normalise a chapter (dict or Pydantic model) to a plain dict."""
    if isinstance(ch, dict):
        return {
            "id": ch.get("id"),
            "chapter_no": ch.get("chapter_no"),
            "processed_pages": ch.get("processed_pages") or 0,
        }
    return {
        "id": str(getattr(ch, "id", "")),
        "chapter_no": getattr(ch, "chapter_no", None),
        "processed_pages": getattr(ch, "processed_pages", 0) or 0,
    }
