import re
import json
from typing import Dict, Any, Optional
from loguru import logger
from models.llm_gateway import LLMGateway

class MetadataExtractor:
    """Extracts curriculum metadata (board, class, subject, chapter, title, difficulty) from document text or filename."""
    def __init__(self) -> None:
        self.gateway = LLMGateway()

    def parse_filename_heuristics(self, filename: str, filepath: str = "") -> Dict[str, Any]:
        """Parses common textbook filename schemas, e.g. 'aejm101.pdf' or 'Math_1_Chapter_1.pdf'."""
        metadata = {
            "board": "NCERT",
            "class": "1",
            "subject": "Mathematics",
            "chapter": "1",
            "title": "Chapter 1",
            "book_title": "Mathematics Class 1"
        }
        
        # Extract folder name from filepath if available
        if filepath:
            norm_path = filepath.replace("\\", "/")
            dir_parts = norm_path.split("/")
            
            # If path format is like 'data/class_10/Science/jesc101.pdf', check the parts
            if len(dir_parts) >= 3:
                class_part = dir_parts[-3]
                sub_part = dir_parts[-2]
                
                class_match = re.search(r'class_(\d+)', class_part.lower())
                if class_match:
                    metadata["class"] = class_match.group(1)
                    
                sub_lower = sub_part.lower()
                if "math" in sub_lower:
                    metadata["subject"] = "Mathematics"
                elif "science" in sub_lower or "sci" in sub_lower:
                    metadata["subject"] = "Science"
                elif "history" in sub_lower:
                    metadata["subject"] = "History"
                elif "geo" in sub_lower:
                    metadata["subject"] = "Geography"
                elif "civic" in sub_lower or "pol" in sub_lower:
                    metadata["subject"] = "Civics"
                elif "econ" in sub_lower:
                    metadata["subject"] = "Economics"
                elif "hindi" in sub_lower:
                    metadata["subject"] = "Hindi"
                elif "english" in sub_lower:
                    metadata["subject"] = "English"
                else:
                    metadata["subject"] = sub_part.capitalize()
            elif len(dir_parts) == 2:
                # Fallback to check parent folder
                parent_name = dir_parts[-2]
                if parent_name:
                    parts = re.split(r'[_-]', parent_name)
                    if parts:
                        sub = parts[0]
                        sub_lower = sub.lower()
                        if "math" in sub_lower:
                            metadata["subject"] = "Mathematics"
                        elif "sci" in sub_lower:
                            metadata["subject"] = "Science"
                        elif "hist" in sub_lower:
                            metadata["subject"] = "History"
                        elif "geo" in sub_lower:
                            metadata["subject"] = "Geography"
                        else:
                            metadata["subject"] = sub.capitalize()
                            
                        if len(parts) > 1 and parts[1].isdigit():
                            metadata["class"] = parts[1]
            
            metadata["book_title"] = f"{metadata['subject']} Class {metadata['class']}"

        # Match 'aejm101' where 'ae' is book code, 'j' is lang, 'm' is math, '1' is class, '01' is chapter
        name_lower = filename.lower()
        stem = filename.rsplit('.', 1)[0].lower()
        
        ncert_match = re.match(r'^[a-z]{4}\d(\d{2})$', stem)
        if ncert_match:
            ch_num = int(ncert_match.group(1))
            metadata["chapter"] = str(ch_num)
            metadata["title"] = f"Chapter {metadata['chapter']}"
            
            # Resolve official NCERT chapter title if available
            try:
                from pathlib import Path
                reg_file = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ncert_official_chapters.json"
                if reg_file.exists():
                    with open(reg_file, "r", encoding="utf-8") as f:
                        registry = json.load(f)
                        sub_dict = registry.get(metadata.get("subject", "Mathematics"), {})
                        cls_titles = sub_dict.get(str(metadata.get("class", "8")), [])
                        if 1 <= ch_num <= len(cls_titles):
                            metadata["title"] = cls_titles[ch_num - 1]
            except Exception:
                pass
        else:
            if re.search(r'aejm1(\d{2})', name_lower):
                match = re.search(r'aejm1(\d{2})', name_lower)
                metadata["class"] = "1"
                metadata["subject"] = "Mathematics"
                metadata["chapter"] = str(int(match.group(1)))
                metadata["title"] = f"Mathematics Class 1 Chapter {metadata['chapter']}"
                return metadata
                
            # Class and chapter regexes
            class_match = re.search(r'class[_\-\s]*(\d+)', name_lower)
            if class_match:
                metadata["class"] = class_match.group(1)
                
            chapter_match = re.search(r'chapter[_\-\s]*(\d+)', name_lower)
            if chapter_match:
                metadata["chapter"] = chapter_match.group(1)
            else:
                # Fallback: check any digits at the end of the filename before .pdf
                end_digits = re.search(r'(\d+)\.pdf$', name_lower)
                if end_digits:
                    metadata["chapter"] = str(int(end_digits.group(1)))
                
            if "math" in name_lower:
                metadata["subject"] = "Mathematics"
            elif "sci" in name_lower:
                metadata["subject"] = "Science"
                
        if "book_title" not in metadata or not metadata["book_title"]:
            metadata["book_title"] = f"{metadata['subject']} Class {metadata['class']}"

        return metadata

    async def extract_metadata_from_text(self, first_page_text: str, filename_heuristics: Dict[str, Any]) -> Dict[str, Any]:
        """Queries the LLM to extract structured metadata from the first page text of a chapter."""
        if not first_page_text.strip():
            return filename_heuristics

        prompt = f"""
Analyze the following text extracted from the beginning/first page of an educational document.
Extract the metadata details and output them strictly as a JSON object with the following keys:
- "title": (string, name of the chapter or document, e.g. "Shapes and Space" or "Chemical Reactions")
- "book_title": (string, general name of the textbook, e.g. "Math Magic" or "Science")
- "subject": (string, e.g., Mathematics, Science, History)
- "class": (string/number, class level, e.g., "1", "10")
- "board": (string, e.g., "NCERT", "CBSE", "ICSE")
- "chapter": (string/number, e.g., "1", "4")
- "difficulty": (string, "Easy", "Medium", or "Hard")

Use the heuristics {json.dumps(filename_heuristics)} as a fallback if the text does not contain some fields.

Text:
{first_page_text[:1500]}

JSON Output:
"""
        try:
            response = await self.gateway.generate(
                prompt=prompt,
                max_retries=2,
                temperature=0.1
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group(0))
                # Validate fields, merge with heuristics
                result = {**filename_heuristics, **extracted}
                
                # Sanitize class field
                heur_class = self._clean_class_level(filename_heuristics.get("class"))
                ext_class = self._clean_class_level(extracted.get("class"))
                
                final_class = ext_class if ext_class is not None else heur_class
                if final_class is None:
                    final_class = 1
                result["class"] = str(final_class)
                
                logger.info(f"LLM successfully extracted metadata: {result}")
                return result
        except Exception as e:
            logger.error(f"Failed to extract metadata via LLM: {e}. Falling back to heuristics.")
            
        heur_class = self._clean_class_level(filename_heuristics.get("class"))
        filename_heuristics["class"] = str(heur_class if heur_class is not None else 1)
        return filename_heuristics

    def _clean_class_level(self, class_val: Any) -> Optional[int]:
        if class_val is None:
            return None
        s = str(class_val).strip().lower()
        s = s.replace("class", "").replace("grade", "").replace("level", "").strip()
        if not s:
            return None
            
        # Roman numeral mapping
        roman_map = {
            "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
            "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
            "xi": 11, "xii": 12
        }
        if s in roman_map:
            return roman_map[s]
            
        # Word mappings
        word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12,
            "primary": 1, "secondary": 9, "senior secondary": 11,
            "middle": 6, "high": 9
        }
        if s in word_map:
            return word_map[s]
            
        # Find first consecutive digits
        import re
        match = re.search(r'\d+', s)
        if match:
            return int(match.group(0))
            
        return None

