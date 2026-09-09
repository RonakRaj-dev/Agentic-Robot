from typing import List, Dict, Any, Optional
from loguru import logger
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult
from ai_teacher_robot.rag.vector_store.qdrant_store import QdrantStore

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None
    CHROMA_AVAILABLE = False

class ChromaStore:
    """Manages semantic vector index operations in Chroma (delegates to QdrantStore fallback if not installed)."""
    def __init__(self, collection_name: str = "curriculum_embeddings", dimension: int = 384) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = None
        self.collection = None
        self.fallback = QdrantStore(collection_name, dimension)
        self._init_client()

    def _init_client(self):
        if not CHROMA_AVAILABLE:
            logger.warning("chromadb is not installed. Defaulting to QdrantStore in-memory fallback.")
            self.client = None
            return

        try:
            self.client = chromadb.Client()
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            logger.info(f"Initialized Chroma collection {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Chroma client: {e}. Defaulting to QdrantStore fallback.")
            self.client = None

    def add_chunks(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]) -> List[str]:
        if self.client and self.collection:
            try:
                import uuid
                ids = []
                documents = []
                metadatas = []
                for idx, chunk in enumerate(chunks):
                    point_id = str(uuid.uuid4())
                    ids.append(point_id)
                    documents.append(chunk.get("chunk_text", ""))
                    
                    metadatas.append({
                        "subject": chunk.get("subject", "General"),
                        "chapter": str(chunk.get("chapter", "1")),
                        "topic": chunk.get("topic", "General"),
                        "page_number": int(chunk.get("page_number", 1)),
                        "document_id": str(chunk.get("document_id", "")),
                        "board": chunk.get("board", "NCERT"),
                        "class": str(chunk.get("class", "1")),
                        "difficulty": chunk.get("difficulty", "Easy"),
                        "chunk_id": str(chunk.get("chunk_id", "")),
                        "curriculum_version": chunk.get("curriculum_version", "2026.1")
                    })
                
                self.collection.add(
                    embeddings=vectors,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                return ids
            except Exception as e:
                logger.error(f"Chroma add failed: {e}. Running fallback.")
        
        return self.fallback.add_chunks(chunks, vectors)

    def search(self, vector: List[float], limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        if self.client and self.collection:
            try:
                # Convert filter to Chroma syntax
                chroma_filter = {}
                if filter_dict:
                    chroma_filter = {k: v for k, v in filter_dict.items()}

                search_res = self.collection.query(
                    query_embeddings=[vector],
                    n_results=limit,
                    where=chroma_filter
                )
                
                results = []
                if search_res and search_res["ids"] and search_res["ids"][0]:
                    ids = search_res["ids"][0]
                    docs = search_res["documents"][0]
                    metas = search_res["metadatas"][0]
                    distances = search_res["distances"][0] if "distances" in search_res else [0.0]*len(ids)
                    
                    for i in range(len(ids)):
                        pay = metas[i]
                        score = 1.0 - distances[i] # Convert distance to similarity score
                        results.append(
                            RetrievalResult(
                                chunk_id=pay.get("chunk_id") or ids[i],
                                document_id=pay.get("document_id", ""),
                                chunk_text=docs[i],
                                page_number=int(pay.get("page_number", 1)),
                                chapter=pay.get("chapter", "1"),
                                topic=pay.get("topic", "General"),
                                score=score,
                                metadata=pay
                            )
                        )
                return results
            except Exception as e:
                logger.error(f"Chroma search failed: {e}. Running fallback.")

        return self.fallback.search(vector, limit, filter_dict)

    def delete_chunks(self, document_id: str) -> bool:
        if self.client and self.collection:
            try:
                self.collection.delete(where={"document_id": document_id})
                return True
            except Exception as e:
                logger.error(f"Chroma delete failed: {e}")
        return self.fallback.delete_chunks(document_id)
