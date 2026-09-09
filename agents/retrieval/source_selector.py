from typing import List, Dict, Any

class SourceSelector:
    """Selects the best/most reliable sources from retrieved chunks and filters low relevance ones."""
    def __init__(self, min_score_threshold: float = 0.35) -> None:
        self.min_score_threshold = min_score_threshold

    def select_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters out sources below threshold and groups by document/chapter for citation."""
        selected = []
        seen_citations = set()

        for chunk in chunks:
            score = chunk.get("combined_score", chunk.get("score", 0.0))
            if score < self.min_score_threshold:
                continue

            # Format distinct citation key: "Class X Subject Chapter Y Page Z"
            chapter = chunk.get("chapter", "Unknown")
            page = chunk.get("page_number", "Unknown")
            citation_key = f"Chapter {chapter}, Page {page}"
            
            if citation_key not in seen_citations:
                seen_citations.add(citation_key)
                selected.append(chunk)

        return selected
