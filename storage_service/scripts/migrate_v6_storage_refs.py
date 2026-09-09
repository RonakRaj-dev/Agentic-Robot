"""v6 → v7 storage-ref migration script.

Walks every BOOKS and EXAMS document in MongoDB and back-fills the
structured storage-ref fields (``*_bucket`` + ``*_object_key``) from
the legacy URL fields (``*_url`` / ``questions_only`` /
``questions_with_answers``).  Idempotent — safe to run multiple times.

Optionally, after back-filling, ``$unset``s the legacy URL fields so
the documents no longer carry stale URLs.  This is the recommended
cleanup step once v7 has been deployed and all consumers have been
migrated to :meth:`IStorageService.get_public_url`.

Usage:
    python scripts/migrate_v6_storage_refs.py [--dry-run] [--db-name NAME] [--unset-legacy-url-fields]

Environment:
    MONGO_URI       — MongoDB connection string (defaults to localhost)
    MONGO_DB_NAME   — Database name (defaults to Ncert_Rag)

What gets back-filled:
    BOOKS.chapters[].pdf_bucket_name       ← parse_storage_url(pdf_object_url)
    BOOKS.chapters[].pdf_object_key        ← parse_storage_url(pdf_object_url)
    BOOKS.chapters[].objects[].bucket_name ← parse_storage_url(object_url)
    BOOKS.chapters[].objects[].object_key  ← parse_storage_url(object_url)
    BOOKS.source_pdf.bucket_name           ← parse_storage_url(object_url)
    BOOKS.source_pdf.object_key            ← parse_storage_url(object_url)
    EXAMS.outputs.questions_only_bucket    ← parse_storage_url(questions_only)
    EXAMS.outputs.questions_only_object_key ← parse_storage_url(questions_only)
    EXAMS.outputs.questions_with_answers_bucket    ← parse_storage_url(questions_with_answers)
    EXAMS.outputs.questions_with_answers_object_key ← parse_storage_url(questions_with_answers)

When ``--unset-legacy-url-fields`` is passed (v7 cleanup), the
following fields are ``$unset`` after back-fill:
    BOOKS.chapters[].pdf_object_url
    BOOKS.chapters[].objects[].object_url
    BOOKS.source_pdf.object_url
    EXAMS.outputs.questions_only
    EXAMS.outputs.questions_with_answers

Records that already have the structured fields populated are skipped
(individual field-level skip, not document-level — so partially-migrated
records are completed).

Run with ``--dry-run`` first to see what would change without writing.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

# Add the project root to sys.path so we can import ncert_db modules.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from utils.oid_utils import parse_storage_url  # noqa: E402


def _has_value(v) -> bool:
    return v is not None and v != ""


def _back_fill_from_url(
    url: Optional[str],
    current_bucket: Optional[str],
    current_key: Optional[str],
) -> Tuple[Optional[str], Optional[str], bool]:
    """Return ``(bucket, key, changed)`` for a single field pair.

    If both structured fields are already populated, returns them
    unchanged with ``changed=False``.  Otherwise parses the URL to
    back-fill the missing ones.
    """
    if _has_value(current_bucket) and _has_value(current_key):
        return current_bucket, current_key, False
    if not _has_value(url):
        return current_bucket, current_key, False
    parsed_b, parsed_k = parse_storage_url(url)
    new_b = current_bucket if _has_value(current_bucket) else parsed_b
    new_k = current_key if _has_value(current_key) else parsed_k
    return new_b, new_k, True


async def migrate_books(
    db, dry_run: bool, unset_legacy_url_fields: bool,
) -> dict:
    """Back-fill (and optionally ``$unset``) storage refs on BOOKS documents.

    Returns a stats dict.
    """
    stats = {
        "books_scanned": 0,
        "chapters_migrated": 0,
        "objects_migrated": 0,
        "source_pdfs_migrated": 0,
        "books_modified": 0,
        "books_url_fields_unset": 0,
    }
    cursor = db["BOOKS"].find({})
    async for book in cursor:
        stats["books_scanned"] += 1
        modified = False
        unset_legacy = False

        # ── source_pdf ──────────────────────────────────────────────
        sp = book.get("source_pdf")
        if sp and isinstance(sp, dict):
            new_b, new_k, ch = _back_fill_from_url(
                sp.get("object_url"),
                sp.get("bucket_name"),
                sp.get("object_key"),
            )
            if ch:
                sp["bucket_name"] = new_b
                sp["object_key"] = new_k
                modified = True
                stats["source_pdfs_migrated"] += 1
            if unset_legacy_url_fields and _has_value(sp.get("object_url")):
                sp.pop("object_url", None)
                modified = True
                unset_legacy = True

        # ── chapters ────────────────────────────────────────────────
        for ch in book.get("chapters", []) or []:
            # Chapter PDF ref
            new_b, new_k, chg = _back_fill_from_url(
                ch.get("pdf_object_url"),
                ch.get("pdf_bucket_name"),
                ch.get("pdf_object_key"),
            )
            if chg:
                ch["pdf_bucket_name"] = new_b
                ch["pdf_object_key"] = new_k
                modified = True
                stats["chapters_migrated"] += 1
            if unset_legacy_url_fields and _has_value(ch.get("pdf_object_url")):
                ch.pop("pdf_object_url", None)
                modified = True
                unset_legacy = True

            # Page image objects
            for obj in ch.get("objects", []) or []:
                new_b, new_k, chg = _back_fill_from_url(
                    obj.get("object_url"),
                    obj.get("bucket_name"),
                    obj.get("object_key"),
                )
                if chg:
                    obj["bucket_name"] = new_b
                    obj["object_key"] = new_k
                    modified = True
                    stats["objects_migrated"] += 1
                if unset_legacy_url_fields and _has_value(obj.get("object_url")):
                    obj.pop("object_url", None)
                    modified = True
                    unset_legacy = True

        if modified and not dry_run:
            await db["BOOKS"].replace_one({"_id": book["_id"]}, book)
            stats["books_modified"] += 1
            if unset_legacy:
                stats["books_url_fields_unset"] += 1
        elif modified and dry_run:
            stats["books_modified"] += 1
            if unset_legacy:
                stats["books_url_fields_unset"] += 1

    return stats


async def migrate_exams(
    db, dry_run: bool, unset_legacy_url_fields: bool,
) -> dict:
    """Back-fill (and optionally ``$unset``) storage refs on EXAMS documents.

    Returns a stats dict.
    """
    stats = {
        "exams_scanned": 0,
        "exams_modified": 0,
        "exams_url_fields_unset": 0,
    }
    cursor = db["EXAMS"].find({})
    async for exam in cursor:
        stats["exams_scanned"] += 1
        outputs = exam.get("outputs")
        if not isinstance(outputs, dict):
            continue

        modified = False
        unset_legacy = False

        for which in ("questions_only", "questions_with_answers"):
            new_b, new_k, chg = _back_fill_from_url(
                outputs.get(which),
                outputs.get(f"{which}_bucket"),
                outputs.get(f"{which}_object_key"),
            )
            if chg:
                outputs[f"{which}_bucket"] = new_b
                outputs[f"{which}_object_key"] = new_k
                modified = True
            if unset_legacy_url_fields and _has_value(outputs.get(which)):
                outputs.pop(which, None)
                modified = True
                unset_legacy = True

        if modified and not dry_run:
            await db["EXAMS"].update_one(
                {"_id": exam["_id"]},
                {"$set": {"outputs": outputs}},
            )
            stats["exams_modified"] += 1
            if unset_legacy:
                stats["exams_url_fields_unset"] += 1
        elif modified and dry_run:
            stats["exams_modified"] += 1
            if unset_legacy:
                stats["exams_url_fields_unset"] += 1

    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="v6 → v7 storage-ref migration: back-fill structured "
                    "(bucket, object_key) fields from legacy URLs, "
                    "optionally $unset legacy URL fields.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would change without writing to MongoDB.",
    )
    parser.add_argument(
        "--db-name", default=os.getenv("MONGO_DB_NAME", "Ncert_Rag"),
        help="MongoDB database name (default: $MONGO_DB_NAME or Ncert_Rag)",
    )
    parser.add_argument(
        "--unset-legacy-url-fields", action="store_true",
        help=(
            "After back-filling structured fields, $unset the legacy "
            "URL fields (object_url, pdf_object_url, "
            "questions_only, questions_with_answers) from existing "
            "documents.  Recommended once v7 is deployed and all "
            "consumers use IStorageService.get_public_url."
        ),
    )
    args = parser.parse_args()

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    print(f"\n{'=' * 60}")
    print(f"  v6 → v7 storage-ref migration")
    print(f"{'=' * 60}")
    print(f"  MongoDB URI            : {mongo_uri}")
    print(f"  Database               : {args.db_name}")
    print(f"  Dry-run                : {args.dry_run}")
    print(f"  Unset legacy URL fields: {args.unset_legacy_url_fields}")
    print(f"{'=' * 60}\n")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[args.db_name]

    print("[Step 1] Migrating BOOKS...")
    book_stats = await migrate_books(
        db, dry_run=args.dry_run,
        unset_legacy_url_fields=args.unset_legacy_url_fields,
    )
    print(f"  → books scanned            : {book_stats['books_scanned']}")
    print(f"  → books modified           : {book_stats['books_modified']}")
    print(f"  → chapters migrated        : {book_stats['chapters_migrated']}")
    print(f"  → objects migrated         : {book_stats['objects_migrated']}")
    print(f"  → source_pdfs migrated     : {book_stats['source_pdfs_migrated']}")
    print(f"  → books with URL fields unset: {book_stats['books_url_fields_unset']}")

    print("\n[Step 2] Migrating EXAMS...")
    exam_stats = await migrate_exams(
        db, dry_run=args.dry_run,
        unset_legacy_url_fields=args.unset_legacy_url_fields,
    )
    print(f"  → exams scanned              : {exam_stats['exams_scanned']}")
    print(f"  → exams modified             : {exam_stats['exams_modified']}")
    print(f"  → exams with URL fields unset: {exam_stats['exams_url_fields_unset']}")

    print(f"\n{'=' * 60}")
    if args.dry_run:
        print("  DRY RUN — no changes written. Re-run without --dry-run to apply.")
    else:
        print("  Migration complete.")
    print(f"{'=' * 60}\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
