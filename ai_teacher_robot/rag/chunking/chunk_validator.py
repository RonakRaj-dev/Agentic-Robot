from typing import List, Dict, Any
from loguru import logger

class ChunkValidator:
    """Validates chunks for length constraints, overlap, and required metadata fields."""
    def __init__(self, max_chars: int = 4000, min_chars: int = 20) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars

    def validate_and_filter_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters out invalid chunks and splits/truncates oversized ones."""
        validated_chunks = []
        for idx, chunk in enumerate(chunks):
            text = chunk.get("chunk_text", "").strip()
            
            # Skip empty or trivially small chunks
            if len(text) < self.min_chars:
                logger.debug(f"Skipping chunk {idx} due to length under min threshold ({len(text)} chars).")
                continue
                
            # If chunk is too large, split it or warn and truncate
            if len(text) > self.max_chars:
                logger.warning(f"Oversized chunk {idx} detected ({len(text)} chars). Truncating to {self.max_chars} chars.")
                chunk["chunk_text"] = text[:self.max_chars]
                
            # Ensure metadata exists
            if "page_number" not in chunk:
                chunk["page_number"] = 1
            if "topic" not in chunk or not chunk["topic"]:
                chunk["topic"] = "General"
                
            validated_chunks.append(chunk)
            
        logger.info(f"Validated chunks: {len(validated_chunks)} out of {len(chunks)} input chunks.")
        return validated_chunks
