"""Verification script for testing real dynamic chapter retrieval from MongoDB Atlas across all classes.
"""

from __future__ import annotations
import asyncio
import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv()

from api.routes_query import get_chapters_endpoint, get_subjects_endpoint

async def run_manual_retrieval_verification():
    print("=" * 90)
    print("      REAL MONGODB CHAPTER RETRIEVAL MANUAL VERIFICATION REPORT")
    print("=" * 90)

    total_chapters = 0
    total_subjects = 0

    for cls in range(1, 11):
        subj_res = await get_subjects_endpoint(class_level=cls)
        subjects = subj_res.get("subjects", []) if isinstance(subj_res, dict) else subj_res
        print(f"\n[CLASS {cls}] Found {len(subjects)} Subjects: {', '.join(subjects)}")

        for subj in subjects:
            total_subjects += 1
            chapters = await get_chapters_endpoint(class_level=cls, subject=subj)
            ch_cnt = len(chapters)
            total_chapters += ch_cnt

            if chapters:
                sample_titles = [c["title"].replace(f"Chapter {c['chapterNumber']}: ", "") for c in chapters[:3]]
                first_title = chapters[0]["title"]
                is_placeholder = "Fundamental" in first_title or "Core Applications" in first_title
                status = "❌ PLACEHOLDER" if is_placeholder else "✅ REAL DATA"
                print(f"   • Subject: {subj:<22} | Chapters: {ch_cnt:<3} | Status: {status}", flush=True)
                print(f"     Samples: {', '.join(sample_titles)}", flush=True)
            else:
                print(f"   • Subject: {subj:<22} | Chapters: 0   | Status: ⚠️ EMPTY", flush=True)

    print("\n" + "=" * 90)
    print(f"FINAL AUDIT TOTAL: {total_subjects} Subjects Verified | {total_chapters} Total Real Chapters Retrieved")
    print("=" * 90)

if __name__ == "__main__":
    asyncio.run(run_manual_retrieval_verification())
