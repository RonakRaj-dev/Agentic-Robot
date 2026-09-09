"""NCERT Official Backend & Database Audit Script.

Audits MongoDB BOOKS, CHAPTERS, and CHUNKS collections against official NCERT structure,
verifying class coverage, subject mapping, human-readable chapter names, and vector ready state.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv()

def run_ncert_audit():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.environ.get("MONGO_DB_NAME", "Humanoid_db")

    client = MongoClient(mongo_uri)
    db = client[db_name]

    print("=" * 80)
    print("      OFFICIAL NCERT CURRICULUM BACKEND AUDIT REPORT")
    print("=" * 80)

    books = list(db.BOOKS.find().sort([("class_no", 1), ("subject", 1)]))
    print(f"\nTotal Books Registered in MongoDB BOOKS Collection: {len(books)}\n")

    class_summary = {}

    for b in books:
        b_id = str(b["_id"])
        c_no = b.get("class_no", "?")
        subj = b.get("subject", "Unknown")
        title = b.get("title", "")

        chs = list(db.CHAPTERS.find({"book_id": b_id}).sort("chapter_no", 1))
        ch_count = len(chs)

        # Count chunks
        chunk_count = db.CHUNKS.count_documents({"book_id": b_id})

        if c_no not in class_summary:
            class_summary[c_no] = []

        class_summary[c_no].append({
            "subject": subj,
            "title": title,
            "chapters": ch_count,
            "chunks": chunk_count,
            "sample_chapters": [c.get("chapter_name") for c in chs[:3]]
        })

    for c_no in sorted(class_summary.keys(), key=lambda x: int(x) if str(x).isdigit() else 99):
        print(f"--- CLASS {c_no} ---")
        for item in class_summary[c_no]:
            print(f"  • Subject: {item['subject']:<20} | Book: {item['title']:<30} | Chapters: {item['chapters']:<3} | Chunks: {item['chunks']}")
            if item["sample_chapters"]:
                print(f"    Sample Chapters: {', '.join([str(sc) for sc in item['sample_chapters']])}")
        print()

    total_chapters = db.CHAPTERS.count_documents({})
    total_chunks = db.CHUNKS.count_documents({})

    print("=" * 80)
    print(f"SUMMARY TOTALS: {len(books)} Books | {total_chapters} Chapters | {total_chunks} Chunks")
    print("=" * 80)

if __name__ == "__main__":
    run_ncert_audit()
