"""CLI ingestion script — single PDF ingestion via PyMuPDF.

For catalog-driven batch ingestion, use ``ingest_catalog.py`` instead.

Usage:
    python ingest.py <pdf_path> --title TITLE --class CLASS --subject SUBJECT [options]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from factory import build_real_pipeline
from models.ingestion_input import IngestionInput, BookMetadata
from utils.progress_utils import ConsoleProgressCallback

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def build_pipeline(progress_callback=None):
    """Wire the pipeline via the factory (real Mongo + MinIO + PyMuPDF)."""
    return build_real_pipeline(progress_callback=progress_callback)


def parse_args():
    p = argparse.ArgumentParser(
        description="Ingest a single PDF into MongoDB + MinIO (PyMuPDF)"
    )
    p.add_argument("pdf", type=Path, help="Path to the PDF file")
    p.add_argument("--title", required=True, help="Book title")
    p.add_argument("--class", dest="class_level", required=True, help='Class level, e.g. "10"')
    p.add_argument("--subject", required=True, help='Subject, e.g. "Maths"')
    p.add_argument("--author", default=None)
    p.add_argument("--publisher", default=None)
    p.add_argument("--board", default="NCERT")
    p.add_argument("--language", default="en")
    p.add_argument("--json", action="store_true", help="Print full result as JSON")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    return p.parse_args()


async def main():
    args = parse_args()

    if not args.pdf.exists():
        print(f"ERROR: PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)
    if args.pdf.suffix.lower() != ".pdf":
        print(f"ERROR: File must be a .pdf, got: {args.pdf.suffix}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  PDF     : {args.pdf}")
    print(f"  Title   : {args.title}")
    print(f"  Class   : {args.class_level}  Subject: {args.subject}  Board: {args.board}")
    print(f"  Engine  : PyMuPDF")
    print(f"{'=' * 60}\n")

    progress = ConsoleProgressCallback(verbose=not args.quiet)
    pipeline = build_pipeline(progress_callback=progress)

    input_data = IngestionInput(
        pdf_path=args.pdf,
        book_metadata=BookMetadata(
            title=args.title,
            author=args.author,
            publisher=args.publisher,
        ),
        class_level=args.class_level,
        subject=args.subject,
        language=args.language,
        board=args.board,
    )

    result = await pipeline.ingest(input_data)

    print(f"\n{'=' * 60}")
    print(f"  Status     : {result.pipeline_status}")
    print(f"  Pages      : {result.pages_processed}/{result.total_pages} processed"
          + (f", {result.pages_failed} failed" if result.pages_failed else ""))
    print(f"  Time       : {result.processing_time_seconds}s")
    print(f"  Book ID    : {result.book_id}")
    print(f"{'=' * 60}\n")

    if result.errors:
        print("ERRORS:")
        for e in result.errors:
            page = f" (page {e.page_number})" if e.page_number else ""
            print(f"  [{e.stage}{page}] {e.error_type}: {e.error_message}")
        print()

    if args.json:
        print(json.dumps(json.loads(result.model_dump_json()), indent=2))

    return 0 if result.pipeline_status == "completed" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
