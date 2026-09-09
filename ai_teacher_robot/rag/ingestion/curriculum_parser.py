import re
from typing import List, Dict, Any

class CurriculumParser:
    """Parses text layout and content to structure topics and subtopics from curriculum files."""
    def __init__(self) -> None:
        pass

    def parse_topics(self, page_text: str) -> List[Dict[str, Any]]:
        """Parses a page text and finds distinct sections or topics with their text blocks."""
        # Simple heuristic: look for lines starting with "1. ", "1.2 ", "Section ", or uppercase headings
        lines = page_text.split("\n")
        topics = []
        current_topic = "General"
        current_content = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Match patterns like: "1.2 Shapes around us", "CHAPTER 1", "Section 2"
            is_heading = False
            if re.match(r'^\d+(\.\d+)+\s+[A-Z]', stripped): # 1.2 Shapes
                is_heading = True
            elif re.match(r'^(section|chapter|topic)\s+\d+', stripped, re.IGNORECASE):
                is_heading = True
            elif len(stripped) < 60 and stripped.isupper() and not stripped.endswith(('.', ',')):
                # Short uppercase lines are often headings
                is_heading = True

            if is_heading:
                # Save previous topic if it has content
                if current_content:
                    topics.append({
                        "topic": current_topic,
                        "text": "\n".join(current_content)
                    })
                current_topic = stripped
                current_content = [stripped]
            else:
                current_content.append(line)

        # Append last one
        if current_content:
            topics.append({
                "topic": current_topic,
                "text": "\n".join(current_content)
            })

        # If no headings were found, return the whole text as one general topic
        if not topics:
            topics.append({
                "topic": "General",
                "text": page_text
            })

        return topics
