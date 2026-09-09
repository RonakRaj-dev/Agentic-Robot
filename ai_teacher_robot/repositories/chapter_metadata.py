"""NCERT Chapter Metadata and Author Catalog Repository.
Provides dynamic author, title, and overview metadata for NCERT chapters.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import re

# Comprehensive NCERT Chapter Author & Metadata Registry
NCERT_CHAPTER_METADATA: Dict[str, Dict[int, Dict[str, Any]]] = {
    # Class 7 English (Honeycomb & Poorvi)
    "7_english": {
        1: {"title": "Three Questions", "author": "Leo Tolstoy", "type": "Story"},
        2: {"title": "A Gift of Chappals", "author": "Vasantha Surya", "type": "Story (From 'Mridu in Madras')"},
        3: {"title": "A Gift of Chappals", "author": "Vasantha Surya", "type": "Story (From 'Mridu in Madras')"},
        4: {"title": "Gopal and the Hilsa Fish", "author": "Indian Folktale", "type": "Comic / Story"},
        5: {"title": "The Ashes That Made Trees Bloom", "author": "William Elliot Griffis", "type": "Japanese Folktale"},
        6: {"title": "Quality", "author": "John Galsworthy", "type": "Story"},
        7: {"title": "Expert Detectives", "author": "Sharada Dwivedi", "type": "Story"},
        8: {"title": "The Invention of Vita-Wonk", "author": "Roald Dahl", "type": "Story"}
    },
    # Class 6 English (Honeysuckle & Poorvi)
    "6_english": {
        1: {"title": "Who Did Patrick's Homework?", "author": "Carol Moore", "type": "Story"},
        2: {"title": "How the Dog Found Himself a New Master!", "author": "Folktale", "type": "Story"},
        3: {"title": "Taro's Reward", "author": "Japanese Folktale", "type": "Story"},
        4: {"title": "An Indian - American Woman in Space: Kalpana Chawla", "author": "Biographical Extract", "type": "Biography"},
        5: {"title": "A Different Kind of School", "author": "E.V. Lucas", "type": "Story"},
        6: {"title": "Who I Am", "author": "Various Authors", "type": "Personal Accounts"}
    },
    # Class 8 English (Honeydew)
    "8_english": {
        1: {"title": "The Best Christmas Present in the World", "author": "Michael Morpurgo", "type": "Story"},
        2: {"title": "The Tsunami", "author": "Real Accounts", "type": "Report"},
        3: {"title": "Glimpses of the Past", "author": "S.D. Sawant", "type": "Comic"},
        4: {"title": "Bepin Choudhury's Lapse of Memory", "author": "Satyajit Ray", "type": "Story"},
        5: {"title": "The Summit Within", "author": "H.P.S. Ahluwalia", "type": "Autobiographical Account"}
    },
    # Class 9 English (Beehive)
    "9_english": {
        1: {"title": "The Fun They Had", "author": "Isaac Asimov", "type": "Sci-Fi Story"},
        2: {"title": "The Sound of Music", "author": "Deborah Cowley", "type": "Biography"},
        3: {"title": "The Little Girl", "author": "Katherine Mansfield", "type": "Story"},
        4: {"title": "A Truly Beautiful Mind", "author": "Biographical Essay", "type": "Biography of Albert Einstein"},
        5: {"title": "The Snake and the Mirror", "author": "Vaikom Muhammad Basheer", "type": "Story"}
    },
    # Class 10 English (First Flight)
    "10_english": {
        1: {"title": "A Letter to God", "author": "G.L. Fuentes", "type": "Story"},
        2: {"title": "Nelson Mandela: Long Walk to Freedom", "author": "Nelson Mandela", "type": "Autobiography"},
        3: {"title": "Two Stories about Flying", "author": "Liam O'Flaherty & Frederick Forsyth", "type": "Story"},
        4: {"title": "From the Diary of Anne Frank", "author": "Anne Frank", "type": "Autobiography"},
        5: {"title": "Glimpses of India", "author": "Lucio Rodrigues, Lokesh Abrol & Arup Kumar Datta", "type": "Essays"}
    }
}

def get_chapter_metadata_info(class_no: Any, subject: Optional[str], chapter_no: Any) -> Optional[Dict[str, Any]]:
    """Retrieve official NCERT chapter metadata including title, author, and genre."""
    try:
        c_no = int(str(class_no).strip())
        ch_no = int(str(chapter_no).strip())
        subj_clean = (subject or "").lower().strip()
        
        if "eng" in subj_clean:
            key = f"{c_no}_english"
            if key in NCERT_CHAPTER_METADATA and ch_no in NCERT_CHAPTER_METADATA[key]:
                return NCERT_CHAPTER_METADATA[key][ch_no]
    except Exception:
        pass
    return None
