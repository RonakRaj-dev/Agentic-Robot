import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx

def test_subjects_and_chapters():
    print("[CURRICULUM DATABASE VERIFICATION]")
    
    # 1. Verify subjects for all classes 1-10
    classes = list(range(1, 11))
    
    for cls in classes:
        url = f"http://127.0.0.1:8000/api/subjects?class={cls}"
        try:
            res = httpx.get(url)
            if res.status_code == 200:
                data = res.json()
                print(f"Class {cls}: {data.get('subjects')}")
            else:
                print(f"Class {cls} GET subjects failed: {res.status_code}")
        except Exception as e:
            print(f"Class {cls} GET subjects exception: {e}")
            
    # 2. Verify chapters retrieval for major classes
    test_cases = [
        (6, "Science"),
        (6, "Mathematics"),
        (8, "Science"),
        (10, "Science")
    ]
    
    for cls, subject in test_cases:
        url = f"http://127.0.0.1:8000/api/chapters?class={cls}&subject={subject}"
        try:
            res = httpx.get(url)
            if res.status_code == 200:
                chapters = res.json()
                print(f"\nChapters for Class {cls} {subject} (Count: {len(chapters)}):")
                for ch in chapters[:3]:
                    print(f"  - {ch.get('title')}")
                if len(chapters) > 3:
                    print("  - ...")
            else:
                print(f"Class {cls} {subject} GET chapters failed: {res.status_code}")
        except Exception as e:
            print(f"Class {cls} {subject} GET chapters exception: {e}")

if __name__ == "__main__":
    test_subjects_and_chapters()
