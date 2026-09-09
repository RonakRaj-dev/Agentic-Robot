"""Database Payload Sanitizer.

Cleans and updates MongoDB CHAPTERS, CHUNKS, and Qdrant vector payload points,
replacing codenames (e.g. Bemr105, Aemr101) with human-readable official NCERT chapter names.
"""

from __future__ import annotations

import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

def load_official_chapters() -> dict:
    ncert_file = ROOT_DIR / "data" / "ncert_official_chapters.json"
    if ncert_file.exists():
        with open(ncert_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def resolve_title(official_catalog: dict, subject: str, class_no: Any, chapter_no: Any, raw_name: str) -> str:
    subj_dict = official_catalog.get(subject) or {}
    official_list = subj_dict.get(str(class_no)) or subj_dict.get(int(class_no)) or []
    
    try:
        ch_idx = int(chapter_no) - 1
        if 0 <= ch_idx < len(official_list):
            return official_list[ch_idx]
    except Exception:
        pass

    if not re.match(r'^[a-z]{4}\d+$', raw_name, re.IGNORECASE):
        return raw_name

    return f"{subject} Chapter {chapter_no}"

def sanitize_databases():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.environ.get("MONGO_DB_NAME", "Humanoid_db")
    
    logger.info(f"Connecting to MongoDB {mongo_uri} | DB: {db_name}...")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    catalog = load_official_chapters()
    
    # 1. Update CHAPTERS collection
    chapters = list(db.CHAPTERS.find())
    logger.info(f"Sanitizing {len(chapters)} CHAPTER documents...")
    for ch in chapters:
        ch_id = ch["_id"]
        ch_no = ch.get("chapter_no", 1)
        raw_title = ch.get("chapter_name", "")
        subj = ch.get("subject", "English")
        cls_no = ch.get("class_no", 1)
        
        clean_title = resolve_title(catalog, subj, cls_no, ch_no, raw_title)
        db.CHAPTERS.update_one({"_id": ch_id}, {"$set": {"chapter_name": clean_title}})
        
    # 2. Update CHUNKS collection
    chunks = list(db.CHUNKS.find())
    logger.info(f"Sanitizing {len(chunks)} CHUNK documents in MongoDB...")
    for chunk in chunks:
        c_id = chunk["_id"]
        subj = chunk.get("subject", "English")
        cls_no = chunk.get("class", 1)
        ch_no = chunk.get("chapter", chunk.get("chapter_no", 1))
        raw_name = chunk.get("chapter_name", "")
        
        clean_title = resolve_title(catalog, subj, cls_no, ch_no, raw_name)
        
        text = chunk.get("chunk_text", "")
        text_clean = re.sub(r'Chapter \d+: [A-Za-z0-9_]+', f'Chapter {ch_no}: {clean_title}', text)
        
        db.CHUNKS.update_one(
            {"_id": c_id},
            {"$set": {"chapter_name": clean_title, "chunk_text": text_clean}}
        )
        
    logger.info("MongoDB payloads successfully sanitized!")

if __name__ == "__main__":
    sanitize_databases()
