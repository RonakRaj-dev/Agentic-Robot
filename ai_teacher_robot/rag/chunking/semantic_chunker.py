import re
from typing import List, Optional
import numpy as np
from loguru import logger

class SemanticChunker:
    """Chunks text based on semantic similarity of consecutive sentences using an embedding provider."""
    def __init__(self, embedding_provider = None, threshold_percentile: float = 80.0) -> None:
        self.embedding_provider = embedding_provider
        self.threshold_percentile = threshold_percentile

    def split_sentences(self, text: str) -> List[str]:
        """Splits a body of text into clean sentences."""
        # Split on sentence ending punctuation followed by whitespace or linebreaks
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        sentences = self.split_sentences(text)
        if len(sentences) <= 1:
            return [text]

        # If embedding provider is not available, fall back to fixed grouping
        if not self.embedding_provider:
            logger.info("No embedding provider for semantic chunking. Falling back to fixed sentence count grouping (3 sentences per chunk).")
            return self._fallback_chunking(sentences)

        try:
            # Generate embeddings for each sentence
            embeddings = []
            for s in sentences:
                emb = self.embedding_provider.generate_embedding(s)
                embeddings.append(emb)

            # Compute cosine similarities between consecutive sentences
            similarities = []
            for i in range(len(embeddings) - 1):
                vec1 = np.array(embeddings[i])
                vec2 = np.array(embeddings[i+1])
                
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 == 0 or norm2 == 0:
                    similarity = 0.0
                else:
                    similarity = float(np.dot(vec1, vec2) / (norm1 * norm2))
                similarities.append(similarity)

            # Define the splitting threshold using a percentile of distances
            distances = [1.0 - s for s in similarities]
            if not distances:
                return [text]
                
            threshold = float(np.percentile(distances, self.threshold_percentile))
            logger.info(f"Semantic chunking distance threshold: {threshold:.4f}")

            chunks = []
            current_chunk = [sentences[0]]
            for i, dist in enumerate(distances):
                if dist > threshold:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [sentences[i+1]]
                else:
                    current_chunk.append(sentences[i+1])
            
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                
            return chunks

        except Exception as e:
            logger.error(f"Error during semantic chunking: {e}. Falling back to heuristic chunking.")
            return self._fallback_chunking(sentences)

    def _fallback_chunking(self, sentences: List[str]) -> List[str]:
        chunks = []
        # Group sentences in chunks of 3 with 1 sentence overlap
        i = 0
        while i < len(sentences):
            chunk_sentences = sentences[i:i+3]
            chunks.append(" ".join(chunk_sentences))
            i += 2  # 1 sentence overlap
        return chunks
