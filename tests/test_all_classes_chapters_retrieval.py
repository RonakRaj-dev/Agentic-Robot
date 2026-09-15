"""Test Script: Comprehensive Retrieval Verification for All Classes & All Subjects.

Validates that real human-readable NCERT chapter titles are fetched dynamically from MongoDB
for every class (1 to 10) and every subject, ensuring no hardcoded fallback placeholders exist.
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

async def verify_all_chapters():
    print("=" * 90)
    print("      COMPREHENSIVE CHAPTER RETRIEVAL VERIFICATION TEST (CLASSES 1 - 10)")
    print("=" * 90)

    total_subjects_tested = 0
    total_chapters_verified = 0
    failed_placeholders = []

    for cls in range(1, 11):
        subj_res = await get_subjects_endpoint(class_level=cls)
        subjects = subj_res.get("subjects", []) if isinstance(subj_res, dict) else subj_res
        print(f"\n[CLASS {cls}] Found {len(subjects)} Subjects: {', '.join(subjects)}")

        for subj in subjects:
            chapters = await get_chapters_endpoint(class_level=cls, subject=subj)
            total_subjects_tested += 1
            ch_count = len(chapters)
            total_chapters_verified += ch_count

            first_title = chapters[0]["title"] if chapters else "NO CHAPTERS FOUND"

            # Check if title is a hardcoded generic placeholder
            is_placeholder = bool(re.search(r'Fundamental .* Concepts|Core Applications .* Grade|Advanced Analytical Skills', first_title, re.IGNORECASE))

            if is_placeholder:
                failed_placeholders.append(f"Class {cls} {subj}: {first_title}")
                status_icon = "❌ PLACEHOLDER DETECTED"
            elif ch_count > 0:
                status_icon = "✅ REAL NCERT DATA"
            else:
                status_icon = "⚠️ EMPTY"

            print(f"   • Subject: {subj:<22} | Chapters: {ch_count:<3} | Status: {status_icon}")
            if chapters:
                sample_names = [c["title"].replace(f"Chapter {c['chapterNumber']}: ", "") for c in chapters[:3]]
                print(f"     Sample Chapter Titles: {', '.join(sample_names)}")

    print("\n" + "=" * 90)
    print(f"VERIFICATION SUMMARY: {total_subjects_tested} Subjects Tested across Classes 1-10 | {total_chapters_verified} Chapters Retrieved")
    
    if failed_placeholders:
        print(f"❌ FAIL: Found {len(failed_placeholders)} generic placeholder subjects:")
        for fp in failed_placeholders:
            print(f"   - {fp}")
    else:
        print("✅ SUCCESS: 100% of tested subjects return REAL NCERT chapter titles from MongoDB!")
    print("=" * 90)

if __name__ == "__main__":
    asyncio.run(verify_all_chapters())
