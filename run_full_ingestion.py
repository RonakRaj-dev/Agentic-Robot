"""Automated Pipeline: PDF to Markdown Conversion, Schema v4 Storage & Qdrant Ingestion CLI.

Features:
1. Converts PDFs to clean Markdown (.md) via pymupdf4llm & extracts images locally.
2. Structure-Aware + Sliding Window chunking with context headers.
3. Batch persists to MongoDB Schema v4 (BOOKS, CHAPTERS, CHUNKS collections).
4. Generates dense vector embeddings and upserts to Qdrant (curriculum_embeddings).
5. Supports --all flag to automatically process ALL classes and subjects in data/pdfs.
6. Optional --reset-db flag for a clean database baseline before running.

Usage:
    # Ingest ALL classes & subjects in data/pdfs:
    python run_full_ingestion.py --pdf-dir ./data/pdfs --all

    # Ingest specific class and subject:
    python run_full_ingestion.py --pdf-dir ./data/pdfs --class 9 --subject Science
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient

# Load environment variables from .env
load_dotenv()

# Ensure root workspace is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = ROOT_DIR / "storage_service"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(STORAGE_DIR) not in sys.path:
    sys.path.insert(0, str(STORAGE_DIR))

from storage_service.services.pymupdf.pymupdf_service import PyMuPDFService
from storage_service.services.storage.local_storage_service import LocalStorageService
from ai_teacher_robot.rag.chunking.curriculum_chunker import CurriculumChunker
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from ai_teacher_robot.rag.vector_store.qdrant_store import QdrantStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate PDF -> Markdown conversion, MongoDB Schema v4 storage, and Qdrant ingestion."
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        required=True,
        help="Directory containing chapter PDF files to ingest.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Automatically discover and ingest ALL classes and subjects recursively inside pdf-dir.",
    )
    parser.add_argument(
        "--class",
        dest="class_no",
        type=str,
        default="1",
        help="Class level (e.g. 1, 5, 9, 10). Default: 1",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default="English",
        help="Subject name (e.g. English, Hindi, Science, Mathematics). Default: English",
    )
    parser.add_argument(
        "--board",
        type=str,
        default="NCERT",
        help="Educational board. Default: NCERT",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Reset MongoDB collections (BOOKS, CHAPTERS, CHUNKS) and Qdrant collection before ingesting.",
    )
    return parser.parse_args()


def reset_databases(mongo_uri: str, db_name: str) -> None:
    """Drops MongoDB collections and Qdrant collection for a clean ingestion baseline."""
    logger.warning("RESET-DB requested: Dropping old database collections...")
    
    # 1. Mongo Reset
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        db.BOOKS.drop()
        db.CHAPTERS.drop()
        db.CHUNKS.drop()
        logger.info("MongoDB collections (BOOKS, CHAPTERS, CHUNKS) dropped successfully.")
    except Exception as e:
        logger.error(f"Failed to reset MongoDB: {e}")

    # 2. Qdrant Reset
    try:
        from qdrant_client import QdrantClient
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333/")
        qclient = QdrantClient(url=qdrant_url)
        collections = [c.name for c in qclient.get_collections().collections]
        if "curriculum_embeddings" in collections:
            qclient.delete_collection("curriculum_embeddings")
            logger.info("Qdrant collection 'curriculum_embeddings' dropped successfully.")
    except Exception as e:
        logger.error(f"Failed to reset Qdrant: {e}")


def infer_class_and_subject(pdf_path: Path, default_class: str, default_subject: str) -> Tuple[str, str]:
    """Infers class_no and subject from directory structure: .../class_X/SubjectName/filename.pdf"""
    parts = pdf_path.parts
    inferred_class = default_class
    inferred_subject = default_subject

    for idx, part in enumerate(parts):
        if part.startswith("class_"):
            inferred_class = part.replace("class_", "")
            if idx + 1 < len(parts) - 1:
                inferred_subject = parts[idx + 1]
            break

    return inferred_class, inferred_subject


def extract_chapter_title_smart(full_md: str, pdf_stem: str, class_no: str, subject: str, ch_idx: int) -> str:
    import json, re
    # 1. Try resolving against ncert_official_chapters.json
    ncert_file = ROOT_DIR / "data" / "ncert_official_chapters.json"
    if ncert_file.exists():
        try:
            with open(ncert_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                subj_dict = data.get(subject) or {}
                official_list = subj_dict.get(str(class_no)) or subj_dict.get(int(class_no)) or []
                if 0 <= ch_idx - 1 < len(official_list):
                    return official_list[ch_idx - 1]
        except Exception:
            pass

    # 2. Extract from Markdown header
    lines = full_md.splitlines()[:50]
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("![") or "reprint" in line_s.lower() or "isbn" in line_s.lower():
            continue
        if line_s.startswith("#") or line_s.startswith("**") or line_s.startswith(">"):
            clean = re.sub(r'^[#>\s*_]+', '', line_s)
            clean = re.sub(r'[*_#]+$', '', clean).strip()
            clean = re.sub(r'[*_]+', '', clean).strip()
            clean_lower = clean.lower()
            if any(x in clean_lower for x in ["about the unit", "note to the teacher", "contents", "isbn", "reprint", "publication team", "all rights", "before you read"]):
                continue
            if len(clean) > 2 and not clean_lower.startswith("unit"):
                return clean

    # 3. Fallback
    cleaned_stem = pdf_stem.replace("_", " ").title()
    if re.match(r'^[a-z]{4}\d+$', pdf_stem, re.IGNORECASE):
        return f"{subject} Chapter {ch_idx}"
    return cleaned_stem


async def run_automation() -> None:
    args = parse_args()
    pdf_dir: Path = args.pdf_dir

    if not pdf_dir.exists() or not pdf_dir.is_dir():
        logger.error(f"PDF directory not found: {pdf_dir}")
        sys.exit(1)

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.environ.get("MONGO_DB_NAME", "Humanoid_db")

    if args.reset_db:
        reset_databases(mongo_uri, db_name)

    # Gather PDF files grouped by (class_no, subject)
    grouped_pdfs: Dict[Tuple[str, str], List[Path]] = defaultdict(list)

    if args.all:
        logger.info(f"Scanning ALL subfolders recursively in {pdf_dir}...")
        all_pdfs = sorted(list(pdf_dir.rglob("*.pdf")))
        for pdf_path in all_pdfs:
            cls_no, subj = infer_class_and_subject(pdf_path, args.class_no, args.subject)
            grouped_pdfs[(cls_no, subj)].append(pdf_path)
    else:
        # Single targeted folder mode
        target_subfolder = pdf_dir / f"class_{args.class_no}" / args.subject
        if target_subfolder.exists() and target_subfolder.is_dir():
            pdf_files = sorted(list(target_subfolder.glob("*.pdf")))
        else:
            pdf_files = sorted(list(pdf_dir.glob("*.pdf")))
            if not pdf_files:
                pdf_files = sorted(list(pdf_dir.rglob("*.pdf")))

        for pdf_path in pdf_files:
            cls_no, subj = infer_class_and_subject(pdf_path, args.class_no, args.subject)
            grouped_pdfs[(cls_no, subj)].append(pdf_path)

    total_pdf_count = sum(len(files) for files in grouped_pdfs.values())
    if total_pdf_count == 0:
        logger.error(f"No .pdf files found in directory: {pdf_dir}")
        sys.exit(1)

    logger.info(f"Discovered {len(grouped_pdfs)} Book(s) / Subject group(s) containing {total_pdf_count} total PDF(s).")
    logger.info(f"Target DB: {db_name} | Board: {args.board}")

    # Services Setup
    pymupdf_service = PyMuPDFService()
    local_storage = LocalStorageService()
    chunker = CurriculumChunker(max_chunk_tokens=500, overlap_tokens=100)
    embedding_gen = EmbeddingGenerator()
    qdrant_store = QdrantStore(collection_name="curriculum_embeddings", dimension=embedding_gen.get_dimension())

    mongo_client = MongoClient(mongo_uri)
    db = mongo_client[db_name]

    global_total_chunks = 0
    global_total_md_files = 0
    global_start_time = time.time()

    group_idx = 0
    total_groups = len(grouped_pdfs)

    for (class_no, subject), pdf_files in grouped_pdfs.items():
        group_idx += 1
        book_title = f"Class {class_no} {subject} ({args.board})"
        logger.info(f"\n=================================================================")
        logger.info(f"  [BOOK {group_idx}/{total_groups}]: Class {class_no} | Subject: {subject} ({len(pdf_files)} PDFs)")
        logger.info(f"=================================================================")

        # Create Mongo Book entry
        book_doc = {
            "class_no": int(class_no) if class_no.isdigit() else 1,
            "subject": subject,
            "title": book_title,
            "board": args.board,
            "created_at": time.time(),
        }
        
        db.BOOKS.update_one(
            {"class_no": book_doc["class_no"], "subject": subject, "title": book_title},
            {"$set": book_doc},
            upsert=True,
        )
        existing_book = db.BOOKS.find_one({"class_no": book_doc["class_no"], "subject": subject, "title": book_title})
        book_id = str(existing_book["_id"])

        for ch_idx, pdf_path in enumerate(pdf_files, start=1):
            logger.info(f"\n--- Processing [{ch_idx}/{len(pdf_files)}] ({subject}): {pdf_path.name} ---")
            ch_start = time.time()
            chapter_no = ch_idx

            # Step 1: Convert PDF to Markdown & extract images locally via pymupdf4llm
            img_target_dir = local_storage.get_images_dir_for_chapter(book_id, chapter_no)
            extracted = await pymupdf_service.extract_markdown(pdf_path, images_dir=img_target_dir)

            full_md = extracted["full_markdown"]
            total_pages = extracted["total_pages"]

            # Smart chapter title resolution
            chapter_title = extract_chapter_title_smart(full_md, pdf_path.stem, class_no, subject, ch_idx)

            # Step 2: Save Markdown file to local disk (data/markdown/<book_id>/)
            md_file_path = local_storage.save_markdown(book_id, chapter_no, full_md)
            global_total_md_files += 1

            # Step 3: Save Chapter document to MongoDB CHAPTERS collection
            chapter_doc = {
                "book_id": book_id,
                "chapter_no": chapter_no,
                "chapter_name": chapter_title,
                "pdf_path": str(pdf_path),
                "markdown_path": str(md_file_path),
                "images_dir": str(img_target_dir),
                "total_pages": total_pages,
                "word_count": len(full_md.split()),
                "created_at": time.time(),
            }
            db.CHAPTERS.update_one(
                {"book_id": book_id, "chapter_no": chapter_no},
                {"$set": chapter_doc},
                upsert=True,
            )

            # Step 4: Structure-Aware + Sliding Window Chunking
            chunk_meta = {
                "book_title": book_title,
                "class_no": class_no,
                "subject": subject,
                "chapter_no": chapter_no,
                "chapter_name": chapter_title,
                "board": args.board,
            }
            chunks = chunker.chunk_markdown(full_md, metadata=chunk_meta)

            if not chunks:
                logger.warning(f"No chunks extracted from {pdf_path.name}")
                continue

            # Step 5: Compute Embeddings in Batch
            chunk_texts = [c["chunk_text"] for c in chunks]
            vectors = await embedding_gen.generate_embeddings_async(chunk_texts)

            # Step 6: Ingest into MongoDB CHUNKS collection & Qdrant Vector Store
            mongo_chunks_to_insert = []
            for c_idx, (chunk_data, vec) in enumerate(zip(chunks, vectors)):
                chunk_uuid = str(uuid.uuid4())
                chunk_data["chunk_id"] = chunk_uuid
                chunk_data["document_id"] = book_id
                chunk_data["book_id"] = book_id
                chunk_data["chapter_no"] = chapter_no

                mongo_chunks_to_insert.append(chunk_data)

            # Bulk upsert to Mongo CHUNKS
            db.CHUNKS.delete_many({"book_id": book_id, "chapter_no": chapter_no})
            db.CHUNKS.insert_many(mongo_chunks_to_insert)

            # Upsert to Qdrant
            qdrant_store.add_chunks(chunks, vectors)
            global_total_chunks += len(chunks)

            ch_elapsed = time.time() - ch_start
            logger.info(f"Completed chapter {chapter_no} in {ch_elapsed:.2f}s | {len(chunks)} chunks embedded & stored.")

    total_time = time.time() - global_start_time
    print("\n" + "=" * 65)
    print("  ALL CLASSES & SUBJECTS INGESTION COMPLETE")
    print(f"  Processed Books/Subjects: {total_groups}")
    print(f"  Total Processed PDFs    : {total_pdf_count}")
    print(f"  Markdown (.md) Files    : {global_total_md_files} saved in data/markdown/")
    print(f"  Extracted Images        : Saved in data/extracted_images/")
    print(f"  Ingested Chunks         : {global_total_chunks} in MongoDB Atlas & Qdrant")
    print(f"  Total Duration          : {total_time:.2f} seconds")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(run_automation())
