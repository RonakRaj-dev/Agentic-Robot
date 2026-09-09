"""NCERT catalog import service.

Reads the ``newestbooks.json`` master catalog and creates Book documents
in MongoDB with embedded chapter metadata.  Each book entry carries
catalog-driven fields (``pdf_filename``, ``chapter_code``,
``preferred_llm``, ``catalog_source``) that enable deterministic
chapter-to-PDF mapping during the ingestion pipeline — no fuzzy
matching, no LLM inference, no OCR-based chapter name detection.

Idempotency
-----------
Re-running catalog import does NOT create duplicate books.  Before
creating a Book document, the service checks whether a book with the
same (class_no, board, subject, title) already exists.  If it does,
the existing ``book_id`` is returned and chapters are ensured (not
duplicated) via the batched ``add_chapters`` call.

Stable mapping
--------------
During import, the service builds a mapping::

    pdf_filename -> (book_id, chapter_no)

This mapping is stored in-memory and can be used by the ingestion
pipeline to deterministically locate the correct Book and chapter
for any PDF file — no fuzzy matching, no LLM inference.

Batching
--------
For a NEW book, all chapters are pushed in a single ``$push + $each``
via :meth:`IBookService.add_chapters` — one round trip per book
instead of one per chapter.  For an EXISTING book (re-import), each
chapter is ensured individually via :meth:`IBookService.add_chapter`
because the batch ``add_chapters`` skips chapters whose ``chapter_no``
already exists, and we still need to record the chapter in
``chapter_pdf_map`` even if it already exists.

Catalog structure
-----------------
The JSON catalog is organized as::

    {
      "books": {
        <Board>: {
          <Subject Group>: {
            <Class Name>: {
              <Book Name>: {
                "<chapter_no>: <chapter_title>": "<pdf_filename>",
                ...
              }
            }
          }
        }
      }
    }

Class filtering
---------------
Only Class 1 through Class 10 are imported.  Class 11 and Class 12
entries are silently skipped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging import get_logger
from interfaces.book_service import IBookService

logger = get_logger(__name__)

# Regex to parse "1: Real Numbers" or "E1: Development" or "D2: Julius Caesar"
# into (code, title).
_CHAPTER_KEY_RE = re.compile(r"^([A-Za-z]*\d+)\s*:\s*(.+)$")

# Regex to extract class number from "Class 1", "Class 10", etc.
_CLASS_RE = re.compile(r"^Class\s+(\d+)$", re.IGNORECASE)

# Only import Class 1 through Class 10.
_MIN_CLASS = 1
_MAX_CLASS = 10


class CatalogEntry:
    """Parsed representation of a single book from the catalog."""

    __slots__ = (
        "board",
        "subject_group",
        "class_no",
        "book_title",
        "chapters",
    )

    def __init__(
        self,
        board: str,
        subject_group: str,
        class_no: int,
        book_title: str,
        chapters: List[Dict[str, str]],
    ) -> None:
        self.board = board
        self.subject_group = subject_group
        self.class_no = class_no
        self.book_title = book_title
        self.chapters = chapters

    def __repr__(self) -> str:
        return (
            f"CatalogEntry(board={self.board!r}, class_no={self.class_no}, "
            f"book_title={self.book_title!r}, chapters={len(self.chapters)})"
        )


def parse_chapter_key(key: str) -> tuple[str, str]:
    """Parse a catalog chapter key like ``'1: Real Numbers'`` into
    ``(chapter_code, chapter_title)``.

    Returns ``("", key)`` if the key doesn't match the expected pattern.
    """
    m = _CHAPTER_KEY_RE.match(key.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return "", key.strip()


def parse_class_number(class_name: str) -> Optional[int]:
    """Extract the numeric class level from a string like ``'Class 10'``.

    Returns ``None`` if the string doesn't match.
    """
    m = _CLASS_RE.match(class_name.strip())
    if m:
        return int(m.group(1))
    return None


def _chapter_sort_key(ch: Dict[str, str]) -> tuple:
    """Sort key for catalog chapters by chapter_code's numeric part."""
    code = ch.get("chapter_code", "")
    num_match = re.match(r"^(\d+)", code)
    num = int(num_match.group(1)) if num_match else 999
    prefix = re.match(r"^([A-Za-z]*)", code)
    pre = prefix.group(1) if prefix else ""
    return (pre, num, code)


def parse_catalog(catalog_path: Path) -> List[CatalogEntry]:
    """Parse the ``newestbooks.json`` catalog file.

    Returns a list of :class:`CatalogEntry` objects, one per book,
    filtered to Class 1–10 only.
    """
    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries: List[CatalogEntry] = []
    books_data = data.get("books", {})

    for board, subject_groups in books_data.items():
        for subject_group, classes in subject_groups.items():
            for class_name, books in classes.items():
                class_no = parse_class_number(class_name)
                if class_no is None:
                    logger.debug("Skipping non-numeric class: %s", class_name)
                    continue
                if class_no < _MIN_CLASS or class_no > _MAX_CLASS:
                    logger.debug(
                        "Skipping class %d (outside %d-%d range)",
                        class_no, _MIN_CLASS, _MAX_CLASS,
                    )
                    continue

                for book_title, chapters_dict in books.items():
                    chapters: List[Dict[str, str]] = []
                    for chapter_key, pdf_filename in chapters_dict.items():
                        chapter_code, chapter_title = parse_chapter_key(chapter_key)
                        chapters.append({
                            "pdf_filename": pdf_filename,
                            "chapter_code": chapter_code,
                            "chapter_title": chapter_title,
                            "catalog_source": "newestbooks.json",
                        })
                    chapters.sort(key=_chapter_sort_key)
                    entries.append(CatalogEntry(
                        board=board,
                        subject_group=subject_group,
                        class_no=class_no,
                        book_title=book_title,
                        chapters=chapters,
                    ))

    logger.info(
        "Parsed catalog: %d books (Class %d-%d)",
        len(entries), _MIN_CLASS, _MAX_CLASS,
    )
    return entries


class CatalogImportService:
    """Import the NCERT catalog into MongoDB.

    Creates one Book document per :class:`CatalogEntry` with embedded
    chapter metadata.  If a book with the same (class_no, board,
    subject, title) already exists, it is skipped — this makes the
    import **idempotent**.

    After import, a ``pdf_filename → (book_id, chapter_no)`` mapping
    is available via the ``chapter_pdf_map`` attribute.
    """

    def __init__(self, book_service: IBookService) -> None:
        self._books = book_service
        # Stable mapping: pdf_filename -> {"book_id": str, "chapter_no": int}
        self.chapter_pdf_map: Dict[str, Dict[str, Any]] = {}

    async def import_catalog(
        self,
        catalog_path: Path,
    ) -> List[str]:
        """Import the entire catalog (Class 1–10) into MongoDB.

        Returns a list of book_id strings for all created/existing books.
        Re-running this method is idempotent — no duplicate books are
        created.
        """
        entries = parse_catalog(catalog_path)
        book_ids: List[str] = []

        for entry in entries:
            try:
                book_id = await self._import_book(entry)
                if book_id:
                    book_ids.append(book_id)
                    logger.info(
                        "Imported book: class=%d subject=%s title=%s "
                        "(%d chapters) → %s",
                        entry.class_no, entry.subject_group,
                        entry.book_title, len(entry.chapters), book_id,
                    )
            except Exception as exc:
                logger.error(
                    "Failed to import book: class=%d subject=%s title=%s: %s",
                    entry.class_no, entry.subject_group,
                    entry.book_title, exc,
                )

        logger.info(
            "Catalog import complete: %d/%d books imported",
            len(book_ids), len(entries),
        )
        return book_ids

    async def _import_book(self, entry: CatalogEntry) -> Optional[str]:
        """Create or find a Book document with embedded chapter metadata.

        If a book with the same (class_no, board, subject, title) already
        exists, returns the existing book_id without creating a duplicate.
        Chapters are batch-appended via ``add_chapters`` (one round trip).
        """
        # ── Idempotency check: look for existing book ───────────────
        existing_id = await self._books.get_book_by_code(
            class_no=entry.class_no,
            subject=entry.subject_group,
            title=entry.book_title,
            board=entry.board,
        )
        if existing_id:
            logger.info(
                "Book already exists: class=%d subject=%s title=%s → %s (skipping creation)",
                entry.class_no, entry.subject_group,
                entry.book_title, existing_id,
            )
            book_id = existing_id
        else:
            # Create the Book document
            book_id = await self._books.create_book(
                title=entry.book_title,
                class_level=str(entry.class_no),
                subject=entry.subject_group,
                language="en",
                board=entry.board,
                metadata={
                    "catalog_source": "newestbooks.json",
                    "chapter_count": len(entry.chapters),
                    "pdf_filenames": [
                        ch["pdf_filename"] for ch in entry.chapters
                    ],
                },
                pdf_asset_id="",
                total_pages=0,  # Updated later during PDF processing
            )

        # ── Pre-create each chapter with catalog metadata ───────────
        # Build the list of chapter dicts for the batched append.
        chapter_dicts: List[Dict[str, Any]] = []
        for idx, ch_meta in enumerate(entry.chapters, start=1):
            numeric_match = re.match(r"^(\d+)", ch_meta.get("chapter_code", ""))
            if numeric_match:
                chapter_no = int(numeric_match.group(1))
            else:
                chapter_no = idx

            chapter_dicts.append({
                "chapter_no": chapter_no,
                "title": ch_meta.get("chapter_title", f"Chapter {idx}"),
                "pdf_filename": ch_meta.get("pdf_filename"),
                "chapter_code": ch_meta.get("chapter_code"),
                "preferred_llm": ch_meta.get("preferred_llm"),
                "catalog_source": ch_meta.get("catalog_source"),
            })

            # Build the stable pdf_filename → (book_id, chapter_no) mapping.
            pdf_filename = ch_meta.get("pdf_filename")
            if pdf_filename:
                self.chapter_pdf_map[pdf_filename] = {
                    "book_id": book_id,
                    "chapter_no": chapter_no,
                }

        # Batch-append all chapters in a single ``$push + $each``.
        # ``add_chapters`` is idempotent on ``chapter_no`` — chapters
        # that already exist are silently skipped.
        if chapter_dicts:
            await self._books.add_chapters(
                book_id=book_id, chapters=chapter_dicts,
            )

        return book_id
