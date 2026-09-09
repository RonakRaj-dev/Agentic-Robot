import hashlib
from typing import List
import numpy as np
from loguru import logger
from ai_teacher_robot.rag.embedding.embedding_provider import EmbeddingProvider

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

import threading

class EmbeddingGenerator(EmbeddingProvider):
    """Generates text embeddings using sentence-transformers, with offline hash fallback."""
    _shared_model = None
    _shared_initialized = False
    _shared_lock = threading.Lock()

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dimension = 384 # Dimension of 'all-MiniLM-L6-v2'

    def _get_model(self):
        with EmbeddingGenerator._shared_lock:
            if not EmbeddingGenerator._shared_initialized:
                EmbeddingGenerator._shared_initialized = True
                if SENTENCE_TRANSFORMERS_AVAILABLE:
                    try:
                        logger.info(f"Loading local SentenceTransformer model '{self.model_name}'...")
                        EmbeddingGenerator._shared_model = SentenceTransformer(self.model_name)
                        logger.info("SentenceTransformer model loaded successfully.")
                    except Exception as e:
                        logger.warning(f"Failed to load SentenceTransformer model: {e}. Using deterministic hash fallback.")
                        EmbeddingGenerator._shared_model = None
                else:
                    logger.warning("sentence-transformers is not available. Using deterministic hash fallback.")
            return EmbeddingGenerator._shared_model

    def generate_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dimension

        model = self._get_model()
        if model:
            try:
                # Generate embedding locally
                emb = model.encode(text, convert_to_numpy=True)
                return emb.tolist()
            except Exception as e:
                logger.error(f"Error encoding text with SentenceTransformer: {e}. Falling back to deterministic vector.")

        # Fallback: Deterministic vector generation based on MD5 hash of text
        return self._generate_fallback_vector(text)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        model = self._get_model()
        if model:
            try:
                embs = model.encode(texts, convert_to_numpy=True)
                return embs.tolist()
            except Exception as e:
                logger.error(f"Error encoding batch of texts: {e}. Falling back to deterministic vectors.")

        return [self.generate_embedding(t) for t in texts]

    async def generate_embedding_async(self, text: str) -> List[float]:
        import asyncio
        return await asyncio.to_thread(self.generate_embedding, text)

    async def generate_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        return await asyncio.to_thread(self.generate_embeddings, texts)

    def get_dimension(self) -> int:
        return self.dimension

    def _generate_fallback_vector(self, text: str) -> List[float]:
        """Generates a deterministic 384-dimensional unit vector from text hashing."""
        # Use MD5 to get a stable hash seed
        h = hashlib.md5(text.encode("utf-8")).digest()
        # Seed numpy generator for determinism
        seed = int.from_bytes(h[:4], "big")
        rng = np.random.default_rng(seed)
        
        # Generate random values and normalize to unit length
        vec = rng.standard_normal(self.dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
