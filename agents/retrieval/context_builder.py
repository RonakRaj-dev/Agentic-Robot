from typing import List, Dict, Any

class ContextBuilder:
    """Agent context builder: merges chunks and metadata into a formatted instruction prompt context."""
    def __init__(self) -> None:
        pass

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return "No relevant curriculum context found."

        context_blocks = []
        for idx, chunk in enumerate(chunks):
            # Header identifying the source document
            page_info = f"Page {chunk.get('page_number', 'Unknown')}"
            topic_info = f"Topic: {chunk.get('topic', 'General')}"
            chapter_info = f"Chapter: {chunk.get('chapter', 'Unknown')}"
            
            header = f"[Source #{idx + 1}] {chapter_info} | {topic_info} | {page_info}"
            content = chunk.get("chunk_text", "").strip()
            
            context_blocks.append(f"{header}\n---\n{content}\n")

        return "\n\n".join(context_blocks)
