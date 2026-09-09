import re
from loguru import logger

class TextCleaner:
    """Cleans extracted PDF text to remove noise (headers, footers, duplicate spacing, ligatures)."""
    def __init__(self) -> None:
        pass

    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        # 1. Normalize line endings and whitespace
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # 2. Fix hyphenated words broken across lines (e.g. "curric- \nulum" -> "curriculum")
        cleaned = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', cleaned)

        # 3. Replace multiple spaces/tabs with single space, keeping line structures
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)

        # 4. Remove common PDF header/footer noise patterns (like "Page X of Y" or chapter titles at edges)
        # We will strip lines that look exactly like page numbering, e.g. "Page 15" or just numbers at start/end of page
        lines = cleaned.split("\n")
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip page number lines like "Page 1", "12", "Maths - Class X"
            if re.match(r'^(page)?\s*\d+\s*(of\s*\d+)?$', stripped, re.IGNORECASE):
                continue
            if len(stripped) == 0:
                filtered_lines.append("")
                continue
            filtered_lines.append(line)
            
        cleaned = "\n".join(filtered_lines)

        # 5. Fix common spacing issues around punctuation
        cleaned = re.sub(r'\s+([.,;:!?])', r'\1', cleaned)
        
        # 6. Reduce consecutive newlines to maximum of two (preserves paragraphs)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()
