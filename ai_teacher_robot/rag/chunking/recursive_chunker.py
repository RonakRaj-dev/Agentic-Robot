from typing import List

class RecursiveChunker:
    """Splits text recursively using delimiters (paragraphs, sentences, words) to meet size and overlap limits."""
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Splits the text input recursively."""
        if not text:
            return []

        chunks = []
        # Start the recursive splitting
        self._split_recursive(text, self.separators, chunks)
        
        # Merge small chunks to respect overlap and size
        merged_chunks = self._merge_chunks(chunks)
        return merged_chunks

    def _split_recursive(self, text: str, separators: List[str], chunks: List[str]):
        """Helper that does the recursive split on separators."""
        if len(text) <= self.chunk_size:
            chunks.append(text)
            return

        if not separators:
            # If no separators left, hard split by chunk size
            for i in range(0, len(text), self.chunk_size):
                chunks.append(text[i : i + self.chunk_size])
            return

        separator = separators[0]
        if not separator:
            # If empty separator, hard split by chunk size
            for i in range(0, len(text), self.chunk_size):
                chunks.append(text[i : i + self.chunk_size])
            return
            
        splits = text.split(separator)
        
        for part in splits:
            if not part:
                continue
            if len(part) <= self.chunk_size:
                chunks.append(part)
            else:
                self._split_recursive(part, separators[1:], chunks)

    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """Merges small splits together into chunks of self.chunk_size with overlap."""
        merged = []
        current_chunk = []
        current_length = 0

        for chunk in chunks:
            if current_length + len(chunk) + (1 if current_chunk else 0) <= self.chunk_size:
                current_chunk.append(chunk)
                current_length += len(chunk) + 1
            else:
                if current_chunk:
                    merged.append(" ".join(current_chunk))
                
                # Setup next chunk using overlap
                # Backtrack to satisfy overlap
                overlap_text = []
                overlap_len = 0
                for c in reversed(current_chunk):
                    if overlap_len + len(c) + (1 if overlap_text else 0) <= self.chunk_overlap:
                        overlap_text.insert(0, c)
                        overlap_len += len(c) + 1
                    else:
                        break
                
                current_chunk = overlap_text + [chunk]
                current_length = sum(len(c) for c in current_chunk) + len(current_chunk) - 1

        if current_chunk:
            merged.append(" ".join(current_chunk))

        return merged
