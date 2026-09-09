"""CLI ingestion script — catalog-driven batch ingestion using newestbooks.json.

Flow:

    newestbooks.json
        ↓
    Catalog Import  (creates ONE Book per NCERT book)
        ↓
    BOOKS collection  (one document per book, with embedded chapters)
        ↓
    For each chapter PDF:
        find existing book by pdf_filename → ingest_chapter()
        (NO create_book() — appends page images to existing book's chapter)
            ↓
        Upload full chapter PDF to MinIO
        Save PDF reference on EmbeddedChapter
            ↓
        PyMuPDF text extraction (page-by-page)
            ↓
        Render each page as PNG
        Upload page image to MinIO
        Create PAGE_IMAGE object
        Store PAGE_IMAGE inside chapter.objects[]
        Preserve extracted text metadata:
          - plain_text
          - word_count
          - token_count
        Update processed_pages
        Update total_pages
        ↓
    MongoDB Storage

Usage:
    python ingest_catalog.py --catalog /path/to/newestbooks.json --pdf-dir /path/to/pdfs [options]

Examples:
    # Import catalog and process all chapter PDFs (Class 1-10)
    python ingest_catalog.py --catalog newestbooks.json --pdf-dir ./data/pdfs

    # Import catalog only (no PDF processing)
    python ingest_catalog.py --catalog newestbooks.json --import-only
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from core.config import get_settings
from core.logging import configure_logging, get_logger
from factory import build_real_registry
from pipeline.ingestion_pipeline import IngestionPipeline
from services.catalog.catalog_import_service import (
    CatalogImportService,
    parse_catalog,
)
from utils.progress_utils import ConsoleProgressCallback

logger = get_logger(__name__)


async def import_catalog(
    catalog_path: Path,
    book_service,
):
    """Import the catalog and create Book documents in MongoDB.

    This is the ONLY place that creates Book documents.  Re-running is
    idempotent — existing books are skipped.
    """
    importer = CatalogImportService(book_service)
    book_ids = await importer.import_catalog(catalog_path)
    return book_ids, importer


async def process_chapter_pdfs(
    entries: List,
    pdf_dir: Path,
    pipeline: IngestionPipeline,
    book_service,
    chapter_pdf_map: Dict,
    limit: Optional[int] = None,
) -> List[Dict]:
    """Process chapter PDFs by attaching them to EXISTING books.

    Uses the deterministic ``pdf_filename → (book_id, chapter_no)``
    mapping built during catalog import to locate the correct book
    and chapter.  Calls ``pipeline.ingest_chapter()`` which does NOT
    create new books — it uploads the chapter PDF, renders each page
    as a PNG, and appends PAGE_IMAGE objects to the existing chapter's
    ``objects[]`` array.

    ``entries`` is the list of :class:`CatalogEntry` objects from
    :func:`parse_catalog` — the caller parses the catalog once and
    passes the result in so we don't re-read the file.
    """
    results: List[Dict] = []
    processed_count = 0

    for entry in entries:
        if limit and processed_count >= limit:
            break

        for ch_meta in entry.chapters:
            if limit and processed_count >= limit:
                break

            pdf_filename = ch_meta["pdf_filename"]
            pdf_path = pdf_dir / pdf_filename

            if not pdf_path.exists():
                logger.warning("PDF not found (skipping): %s", pdf_path)
                print(f"  SKIP (not found): {pdf_path}")
                continue

            mapping = chapter_pdf_map.get(pdf_filename)
            if mapping is None:
                logger.error(
                    "No catalog mapping for pdf_filename=%s — skipping",
                    pdf_filename,
                )
                results.append({
                    "class_no": entry.class_no,
                    "subject": entry.subject_group,
                    "book": entry.book_title,
                    "chapter": ch_meta.get("chapter_title", ""),
                    "pdf_filename": pdf_filename,
                    "status": "failed",
                    "error": "No catalog mapping found",
                })
                continue

            book_id = mapping["book_id"]
            chapter_no = mapping["chapter_no"]

            try:
                result = await pipeline.ingest_chapter(
                    pdf_path=pdf_path,
                    book_id=book_id,
                    chapter_no=chapter_no,
                )

                results.append({
                    "class_no": entry.class_no,
                    "subject": entry.subject_group,
                    "book": entry.book_title,
                    "chapter": ch_meta.get("chapter_title", ""),
                    "pdf_filename": pdf_filename,
                    "book_id": book_id,
                    "chapter_no": chapter_no,
                    "status": result.pipeline_status,
                    "pages_processed": result.pages_processed,
                    "pages_failed": result.pages_failed,
                    "processing_time": result.processing_time_seconds,
                })
                processed_count += 1

                status_icon = "✓" if result.pipeline_status == "completed" else "✗"
                print(
                    f"  {status_icon} [{entry.class_no}/{entry.subject_group}/"
                    f"{entry.book_title}] Ch{chapter_no} "
                    f"{ch_meta.get('chapter_title', '')} — "
                    f"{result.pages_processed}/{result.total_pages} pages "
                    f"({result.processing_time_seconds:.1f}s)"
                )

            except Exception as exc:
                logger.exception("Failed to process chapter PDF: %s", pdf_filename)
                results.append({
                    "class_no": entry.class_no,
                    "subject": entry.subject_group,
                    "book": entry.book_title,
                    "chapter": ch_meta.get("chapter_title", ""),
                    "pdf_filename": pdf_filename,
                    "book_id": book_id,
                    "chapter_no": chapter_no,
                    "status": "failed",
                    "error": str(exc),
                })
                print(
                    f"  ✗ [{entry.class_no}/{entry.subject_group}/"
                    f"{entry.book_title}] Ch{chapter_no} "
                    f"{ch_meta.get('chapter_title', '')} — ERROR: {exc}"
                )

    return results


def parse_args():
    p = argparse.ArgumentParser(
        description="NCERT catalog-driven batch ingestion (PyMuPDF)"
    )
    p.add_argument("--catalog", type=Path, required=True, help="Path to newestbooks.json")
    p.add_argument("--pdf-dir", type=Path, default=None, help="Root directory for chapter PDFs")
    p.add_argument("--import-only", action="store_true", help="Only import catalog, skip PDF processing")
    p.add_argument("--limit", type=int, default=None, help="Max chapter PDFs to process")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("--json", action="store_true", help="Print results as JSON")
    return p.parse_args()


async def main():
    args = parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    if not args.catalog.exists():
        print(f"ERROR: Catalog file not found: {args.catalog}", file=sys.stderr)
        sys.exit(1)

    entries = parse_catalog(args.catalog)
    total_chapters = sum(len(e.chapters) for e in entries)
    total_books = len(entries)

    print(f"\n{'=' * 70}")
    print(f"  NCERT Catalog-Driven Batch Ingestion")
    print(f"{'=' * 70}")
    print(f"  Catalog     : {args.catalog}")
    print(f"  PDF dir     : {args.pdf_dir or '(not specified)'}")
    print(f"  Engine      : PyMuPDF")
    print(f"  Books       : {total_books} (Class 1-10)")
    print(f"  Chapters    : {total_chapters}")
    print(f"  Import only : {args.import_only}")
    print(f"{'=' * 70}\n")

    # Step 1: Import catalog
    print("[Step 1] Importing catalog (creates ONE Book per NCERT book)...")
    registry = build_real_registry()
    book_service = registry.book_service

    book_ids, importer = await import_catalog(args.catalog, book_service)
    print(f"  → {len(book_ids)} books in database (no duplicates)\n")

    if args.import_only:
        print("Catalog import complete (--import-only specified).")
        return 0

    if not args.pdf_dir:
        print("ERROR: --pdf-dir is required for PDF processing.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Process chapter PDFs
    print("[Step 2] Processing chapter PDFs with PyMuPDF (attaching to existing books)...")
    pipeline = IngestionPipeline(
        storage_service=registry.storage_service,
        book_service=registry.book_service,
        pymupdf_service=registry.pymupdf_service,
        progress_callback=ConsoleProgressCallback(verbose=not args.quiet),
    )

    # Reuse the already-parsed ``entries`` — don't re-read the catalog file.
    results = await process_chapter_pdfs(
        entries=entries,
        pdf_dir=args.pdf_dir,
        pipeline=pipeline,
        book_service=book_service,
        chapter_pdf_map=importer.chapter_pdf_map,
        limit=args.limit,
    )

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") != "completed")
    total_pages = sum(r.get("pages_processed", 0) for r in results)

    unique_book_ids = set(r.get("book_id") for r in results if r.get("book_id"))
    final_book_count = len(unique_book_ids) if unique_book_ids else len(book_ids)

    print(f"\n{'=' * 70}")
    print(f"  RESULTS")
    print(f"{'=' * 70}")
    print(f"  Chapters processed : {len(results)}")
    print(f"  Completed          : {completed}")
    print(f"  Failed             : {failed}")
    print(f"  Total pages        : {total_pages}")
    print(f"  Books in DB        : {final_book_count} (should be {total_books})")
    print(f"{'=' * 70}\n")

    if args.json:
        print(json.dumps(results, indent=2, default=str))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
