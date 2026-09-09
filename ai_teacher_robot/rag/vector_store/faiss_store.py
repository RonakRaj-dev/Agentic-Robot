from typing import List, Dict, Any, Optional
from loguru import logger
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult
from ai_teacher_robot.rag.vector_store.qdrant_store import QdrantStore

try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False

class FaissStore:
    """Manages semantic vector index operations in FAISS (delegates to QdrantStore fallback if not installed)."""
    def __init__(self, collection_name: str = "curriculum_embeddings", dimension: int = 384) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.index = None
        self.fallback = QdrantStore(collection_name, dimension)
        self._init_client()

    def _init_client(self):
        if not FAISS_AVAILABLE:
            logger.warning("faiss is not installed. Defaulting to QdrantStore in-memory fallback.")
            return

        try:
            self.index = faiss.IndexFlatIP(self.dimension) # Inner Product for cosine similarity
            logger.info("Initialized FAISS index flat IP.")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS index: {e}. Defaulting to QdrantStore fallback.")
            self.index = None

    def add_chunks(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]) -> List[str]:
        if self.index is not None and FAISS_AVAILABLE:
            try:
                import uuid
                ids = []
                data = np.array(vectors).astype('float32')
                # L2 normalize vectors for Cosine similarity
                faiss.normalize_L2(data)
                self.index.add(data)
                
                # Keep tracking metadata in fallback memory list because FAISS index flat doesn't store payload metadata!
                self.fallback.add_chunks(chunks, vectors)
                
                for _ in chunks:
                    ids.append(str(uuid.uuid4()))
                return ids
            except Exception as e:
                logger.error(f"FAISS add failed: {e}. Running fallback.")
        
        return self.fallback.add_chunks(chunks, vectors)

    def search(self, vector: List[float], limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        if self.index is not None and FAISS_AVAILABLE and not filter_dict: # FAISS doesn't support metadata filtering natively
            try:
                query = np.array([vector]).astype('float32')
                faiss.normalize_L2(query)
                distances, indices = self.index.search(query, limit)
                
                results = []
                # Reconstruct RetrievalResults using fallback's memory list
                for i in range(len(indices[0])):
                    idx = indices[0][i]
                    if idx == -1 or idx >= len(self.fallback._memory_db):
                        continue
                    item = self.fallback._memory_db[idx]
                    pay = item["payload"]
                    results.append(
                        RetrievalResult(
                            chunk_id=pay.get("chunk_id") or item["id"],
                            document_id=pay.get("document_id", ""),
                            chunk_text=pay.get("chunk_text", ""),
                            page_number=int(pay.get("page_number", 1)),
                            chapter=pay.get("chapter", "1"),
                            topic=pay.get("topic", "General"),
                            score=float(distances[0][i]),
                            metadata=pay
                        )
                    )
                return results
            except Exception as e:
                logger.error(f"FAISS search failed: {e}. Running fallback.")

        # Fallback handle filtering
        return self.fallback.search(vector, limit, filter_dict)

    def delete_chunks(self, document_id: str) -> bool:
        # FAISS doesn't support easy deletion by ID (IndexFlat needs reconstruction)
        # So we rebuild FAISS using fallback list
        res = self.fallback.delete_chunks(document_id)
        if self.index is not None and FAISS_AVAILABLE:
            try:
                self.index.reset()
                if self.fallback._memory_db:
                    vectors = [item["vector"] for item in self.fallback._memory_db]
                    data = np.array(vectors).astype('float32')
                    faiss.normalize_L2(data)
                    self.index.add(data)
                return True
            except Exception as e:
                logger.error(f"FAISS reset/rebuild failed: {e}")
        return res
