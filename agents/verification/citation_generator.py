from typing import List, Dict, Any

class CitationGenerator:
    """Generates standard references and academic citations for retrieved source documents."""
    def __init__(self) -> None:
        pass

    def generate_citations(self, chunks: List[Dict[str, Any]]) -> List[str]:
        citations = []
        seen = set()
        
        for chunk in chunks:
            board = chunk.get("board") or "NCERT"
            subject = chunk.get("subject") or "General"
            class_lvl = chunk.get("class") or chunk.get("class_no") or chunk.get("class_level") or "1"
            chapter = chunk.get("chapter") or chunk.get("chapter_no") or "Unknown"
            page_no = chunk.get("page_number") or "1"
            topic = chunk.get("topic") or "General"
            
            citation_str = f"{board} {subject} Class {class_lvl}, Chapter {chapter} (Page {page_no}) - Topic: {topic}"
            if citation_str not in seen:
                seen.add(citation_str)
                citations.append(citation_str)

        return citations
