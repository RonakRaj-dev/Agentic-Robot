"""Standalone PyMongo Ingestion Script for MongoDB database `SiliconRag`.

Recursively processes all PDF textbooks in `data/`, applies text cleaning and
normalization (NFKC, boilerplate removal, paragraph joining), extracts Table
of Contents metadata from preliminary section PDFs (*ps.pdf), and ingests
structured aggregate Book documents into MongoDB `SiliconRag.BOOKS`.

Usage:
    python ingest_silicon_rag.py [options]

Options:
    --data-dir PATH     Path to data directory (default: ./data)
    --db DB_NAME        MongoDB Database name (default: SiliconRag)
    --collection NAME   MongoDB Collection name (default: BOOKS)
    --dry-run           Run processing without inserting into MongoDB
    --class-filter N    Limit processing to a specific class (e.g. 1)
"""

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bson
import fitz  # PyMuPDF
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


# ---------------------------------------------------------------------------
# Text Normalization & Cleaning Pipeline
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Apply Unicode NFKC normalization and clean non-standard whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Replace non-breaking spaces, thin spaces, soft hyphens
    text = text.replace("\xa0", " ").replace("\u2009", " ").replace("\xad", "")
    return text


def strip_boilerplate(text: str) -> str:
    """Filter out recurring page headers, footers, teacher notes, reprint tags."""
    if not text:
        return ""

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        # Filter Reprint year footers (e.g., Reprint 2026-27)
        if re.match(r"^Reprint\s+\d{4}-\d{2}$", stripped, re.I):
            continue
        # Filter Teacher Notes
        if re.match(r"^Note to the teacher", stripped, re.I):
            continue
        # Filter standalone page numbers at top/bottom margins
        if re.match(r"^\d{1,3}$", stripped) and (len(cleaned_lines) < 2 or len(lines) - lines.index(line) < 3):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def join_paragraphs(text: str) -> str:
    """Replace artificial mid-sentence line breaks with standard spaces.

    Preserves double-newlines for stanza/paragraph separation.
    """
    if not text:
        return ""

    paragraphs = text.split("\n\n")
    joined_paragraphs = []

    for p in paragraphs:
        lines = [l.strip() for l in p.split("\n") if l.strip()]
        if not lines:
            continue
        joined = ""
        for i, line in enumerate(lines):
            if i == 0:
                joined = line
            else:
                if joined.endswith("-"):
                    joined = joined[:-1] + line
                else:
                    joined += " " + line
        joined_paragraphs.append(joined)

    return "\n\n".join(joined_paragraphs)


def process_page_text(raw_text: str) -> Tuple[str, int, int]:
    """Execute full text cleaning pipeline and return (cleaned_text, word_count, token_count)."""
    norm = normalize_text(raw_text)
    stripped = strip_boilerplate(norm)
    cleaned = join_paragraphs(stripped)
    words = cleaned.split()
    word_count = len(words)
    # Estimate token count (~1.33 tokens per word)
    token_count = (word_count * 4) // 3
    return cleaned, word_count, token_count


# ---------------------------------------------------------------------------
# Table of Contents (TOC) Extraction
# ---------------------------------------------------------------------------

def extract_toc_from_ps(ps_path: Path) -> Dict[str, str]:
    """Extract chapter titles from preliminary section PDF (*ps.pdf) if present."""
    chapter_titles: Dict[str, str] = {}
    if not ps_path.exists():
        return chapter_titles

    try:
        doc = fitz.open(ps_path)
        toc_text = ""
        for page in doc:
            p_text = page.get_text()
            if "content" in p_text.lower() or "unit" in p_text.lower() or "chapter" in p_text.lower():
                toc_text += "\n" + p_text

        # Find unit/chapter lines (e.g. Two Little Hands 01 or 1. Two Little Hands)
        lines = [l.strip() for l in toc_text.splitlines() if l.strip()]
        for idx, line in enumerate(lines):
            match = re.search(r"^([A-Za-z\s’'–\-]+)\s+(\d{1,3})$", line)
            if match:
                title = match.group(1).strip()
                page_no = match.group(2)
                if len(title) > 2 and not title.isdigit() and title.lower() not in ["contents", "foreword", "about the book"]:
                    chapter_titles[page_no] = title
    except Exception as err:
        print(f"Warning: Could not parse TOC from {ps_path.name}: {err}", file=sys.stderr)

    return chapter_titles


# ---------------------------------------------------------------------------
# PDF Ingestion Core
# ---------------------------------------------------------------------------

def process_subject_directory(
    class_no: int,
    subject: str,
    subject_dir: Path,
) -> Optional[Dict[str, Any]]:
    """Process all PDFs for a given Class and Subject, producing a single Book aggregate document."""
    pdf_files = sorted([f for f in subject_dir.glob("*.pdf")])
    if not pdf_files:
        return None

    # Separate preliminary section PDF (*ps.pdf)
    ps_file = next((f for f in pdf_files if f.name.endswith("ps.pdf")), None)
    chapter_pdfs = [f for f in pdf_files if not f.name.endswith("ps.pdf")]

    if not chapter_pdfs and ps_file:
        chapter_pdfs = [ps_file]
        ps_file = None

    # Try extracting Table of Contents mapping
    toc_map = extract_toc_from_ps(ps_file) if ps_file else {}

    book_title = f"Class {class_no} {subject.replace('_', ' ').title()}"
    chapters: List[Dict[str, Any]] = []
    total_book_pages = 0

    for ch_idx, pdf_path in enumerate(chapter_pdfs, start=1):
        try:
            doc = fitz.open(pdf_path)
        except Exception as err:
            print(f"ERROR reading {pdf_path}: {err}", file=sys.stderr)
            continue

        num_pages = len(doc)
        total_book_pages += num_pages

        # Determine chapter title
        chapter_title = toc_map.get(str(ch_idx), f"Chapter {ch_idx}")
        if chapter_title == f"Chapter {ch_idx}" and num_pages > 0:
            # Fallback: check page 1 header lines for Unit/Chapter title
            p1_text = doc[0].get_text()
            match = re.search(r"(?:Chapter|Unit)\s*\d+[\s\:\-\n]+([^\n]+)", p1_text, re.I)
            if match:
                chapter_title = match.group(1).strip()

        page_objects: List[Dict[str, Any]] = []
        for p_no in range(1, num_pages + 1):
            raw_text = doc[p_no - 1].get_text()
            cleaned_text, word_cnt, token_cnt = process_page_text(raw_text)

            page_obj = {
                "id": str(bson.ObjectId()),
                "object_type": "PAGE_IMAGE",
                "object_key": f"books/class_{class_no}/{subject.lower()}/chapters/{ch_idx}/page_{p_no:04d}.png",
                "bucket_name": "page-images",
                "object_url": None,
                "page_no": p_no,
                "mime_type": "image/png",
                "size_bytes": 0,  # Metainfo placeholder
                "metadata": {
                    "plain_text": cleaned_text,
                    "word_count": word_cnt,
                    "token_count": token_cnt,
                    "extraction_method": "pymupdf",
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            page_objects.append(page_obj)

        ch_doc = {
            "id": str(bson.ObjectId()),
            "chapter_no": ch_idx,
            "title": chapter_title,
            "pdf_filename": pdf_path.name,
            "chapter_code": str(ch_idx),
            "pdf_object_key": f"books/class_{class_no}/{subject.lower()}/chapters/{ch_idx}/{pdf_path.name}",
            "pdf_bucket_name": "pdfs",
            "pdf_object_url": None,
            "pdf_size_bytes": pdf_path.stat().st_size,
            "processed_pages": num_pages,
            "page_start": 1,
            "page_end": num_pages,
            "objects": page_objects,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        chapters.append(ch_doc)

    book_document = {
        "class_no": class_no,
        "subject": subject.replace("_", " "),
        "title": book_title,
        "board": "NCERT",
        "total_pages": total_book_pages,
        "chapters": chapters,
        "metadata": {
            "source_dir": str(subject_dir),
            "chapter_count": len(chapters),
            "pdf_filenames": [p.name for p in chapter_pdfs],
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    return book_document


# ---------------------------------------------------------------------------
# CLI & Ingestion Runner
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Ingest NCERT PDFs into MongoDB SiliconRag")
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    parser.add_argument("--db", default="SiliconRag", help="Target MongoDB database name")
    parser.add_argument("--collection", default="BOOKS", help="Target collection name")
    parser.add_argument("--dry-run", action="store_true", help="Perform processing without writing to DB")
    parser.add_argument("--class-filter", type=int, default=None, help="Filter by class number")
    return parser.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.data_dir).resolve()
    if not data_path.exists():
        print(f"ERROR: Data directory not found at {data_path}", file=sys.stderr)
        sys.exit(1)

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri and not args.dry_run:
        print("ERROR: MONGO_URI environment variable not set in .env", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("  SiliconRag MongoDB Ingestion Pipeline")
    print(f"  Data Directory : {data_path}")
    print(f"  Database       : {args.db}")
    print(f"  Collection     : {args.collection}")
    print(f"  Dry Run        : {args.dry_run}")
    print("=" * 70 + "\n")

    client = None
    collection = None
    if not args.dry_run:
        client = MongoClient(mongo_uri)
        db = client[args.db]
        collection = db[args.collection]
        # Create unique compound index
        collection.create_index(
            [("class_no", 1), ("board", 1), ("subject", 1), ("title", 1)],
            unique=True,
        )

    class_folders = sorted(
        [d for d in data_path.glob("class_*") if d.is_dir()],
        key=lambda p: int(p.name.split("_")[1]) if p.name.split("_")[1].isdigit() else 0,
    )

    total_books_ingested = 0
    total_pages_ingested = 0

    for class_folder in class_folders:
        try:
            c_no = int(class_folder.name.split("_")[1])
        except ValueError:
            continue

        if args.class_filter is not None and c_no != args.class_filter:
            continue

        print(f"\n--- Processing Class {c_no} ---")
        subject_folders = sorted([d for d in class_folder.iterdir() if d.is_dir()])

        for subj_folder in subject_folders:
            subj_name = subj_folder.name
            book_doc = process_subject_directory(c_no, subj_name, subj_folder)
            if not book_doc:
                continue

            ch_count = len(book_doc["chapters"])
            pg_count = book_doc["total_pages"]
            print(f"  [{subj_name}] -> {ch_count} chapters, {pg_count} total pages extracted")

            if not args.dry_run and collection is not None:
                query = {
                    "class_no": book_doc["class_no"],
                    "board": book_doc["board"],
                    "subject": book_doc["subject"],
                    "title": book_doc["title"],
                }
                collection.replace_one(query, book_doc, upsert=True)

            total_books_ingested += 1
            total_pages_ingested += pg_count

    if client:
        client.close()

    print("\n" + "=" * 70)
    print(f"  Ingestion Complete!")
    print(f"  Total Books Processed : {total_books_ingested}")
    print(f"  Total Pages Extracted : {total_pages_ingested}")
    print("=" * 70)


if __name__ == "__main__":
    main()
