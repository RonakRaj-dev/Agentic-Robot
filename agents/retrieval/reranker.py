import time
import math
import asyncio
from typing import List, Dict, Any

try:
    from sentence_transformers import CrossEncoder
    import torch
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    torch = None
    CROSS_ENCODER_AVAILABLE = False

from loguru import logger


import threading

class Reranker:
    """Fast, optimized Reranker using lightweight cross-encoder with candidate capping & torch.no_grad() threadpool offloading."""
    _shared_model = None
    _shared_initialized = False
    _shared_lock = threading.Lock()

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", max_candidates: int = 10) -> None:
        self.model_name = model_name
        self.max_candidates = max_candidates

    def _get_model(self):
        with Reranker._shared_lock:
            if not Reranker._shared_initialized:
                Reranker._shared_initialized = True
                if CROSS_ENCODER_AVAILABLE:
                    for m_name in [self.model_name, "BAAI/bge-reranker-base", "cross-encoder/ms-marco-MiniLM-L-6-v2"]:
                        try:
                            logger.info(f"Loading CrossEncoder model '{m_name}'...")
                            Reranker._shared_model = CrossEncoder(m_name, max_length=512)
                            logger.info(f"CrossEncoder model '{m_name}' loaded successfully.")
                            break
                        except Exception as e:
                            logger.warning(f"Could not load '{m_name}': {e}. Trying alternative...")
                    if not Reranker._shared_model:
                        logger.warning("All CrossEncoder models failed to load. Using word-overlap fallback.")
                else:
                    logger.warning("sentence-transformers is not installed. Using fallback word-overlap reranker.")
            return Reranker._shared_model

    def rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reranks top candidate chunks using BAAI cross-encoder."""
        if not chunks or not query:
            return chunks

        # Early exit if only 1 item
        if len(chunks) <= 1:
            if chunks:
                chunks[0]["combined_score"] = chunks[0].get("score", 1.0)
            return chunks

        # Limit inference to top candidates to eliminate CPU bottleneck
        top_candidates = chunks[:self.max_candidates]
        tail_candidates = chunks[self.max_candidates:]

        model = self._get_model()
        if model:
            try:
                pairs = [[query, c.get("chunk_text") or c.get("raw_text") or ""] for c in top_candidates]
                
                # Torch no-grad inference for speed
                if torch:
                    with torch.no_grad():
                        scores = model.predict(pairs)
                else:
                    scores = model.predict(pairs)

                for idx, score in enumerate(scores):
                    prob = 1.0 / (1.0 + math.exp(-float(score)))
                    top_candidates[idx]["combined_score"] = prob

                top_candidates.sort(key=lambda x: x["combined_score"], reverse=True)

                for item in tail_candidates:
                    item["combined_score"] = item.get("score", 0.0) * 0.5

                return top_candidates + tail_candidates
            except Exception as e:
                logger.error(f"Error during CrossEncoder prediction: {e}. Falling back to keyword overlap.")

        # Fallback word-overlap scoring
        query_terms = set(query.lower().split())
        scored_chunks = []

        for chunk in chunks:
            text = (chunk.get("chunk_text") or "").lower()
            matched = sum(1 for t in query_terms if t in text)
            overlap_score = matched / len(query_terms) if query_terms else 0.0
            orig_score = chunk.get("score", 0.0)
            chunk["combined_score"] = (orig_score * 0.7) + (overlap_score * 0.3)
            scored_chunks.append(chunk)

        scored_chunks.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored_chunks

    async def rerank_async(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Asynchronously offloads sync CPU cross-encoder inference to thread pool."""
        return await asyncio.to_thread(self.rerank, query, chunks)
