import os
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult

# Ensure .env variables are loaded
load_dotenv()

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PayloadSchemaType
    QDRANT_AVAILABLE = True
except ImportError:
    QdrantClient = None
    PointStruct = None
    Filter = None
    QDRANT_AVAILABLE = False


class QdrantStore:
    """Manages semantic vector index operations in Qdrant server (with local in-memory fallback)."""
    def __init__(self, collection_name: str = "curriculum_embeddings", dimension: int = 384) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = None
        self._memory_db: List[Dict[str, Any]] = []
        self._init_client()

    def _init_client(self):
        if not QDRANT_AVAILABLE:
            logger.warning("qdrant-client is not installed. Using local in-memory list fallback.")
            return

        try:
            qdrant_url = os.environ.get("QDRANT_URL")
            if not qdrant_url and os.environ.get("QDRANT_HOST"):
                host = os.environ.get("QDRANT_HOST", "127.0.0.1")
                port = os.environ.get("QDRANT_PORT", "6333")
                qdrant_url = f"http://{host}:{port}/"

            if qdrant_url:
                logger.info(f"Connecting to Qdrant server at: {qdrant_url}")
                self.client = QdrantClient(url=qdrant_url, timeout=10.0)
            else:
                logger.info("QDRANT_URL not found. Creating native in-memory QdrantClient instance.")
                self.client = QdrantClient(location=":memory:")

            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name} (Dimension: {self.dimension})")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
                
                # Create Payload Indexes for fast metadata filtering
                for field in ["class", "subject", "chapter", "board"]:
                    try:
                        self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name=field,
                            field_schema=PayloadSchemaType.KEYWORD,
                        )
                    except Exception as idx_err:
                        logger.debug(f"Payload index for {field} creation notice: {idx_err}")
                        
        except Exception as e:
            logger.error(f"Failed to initialize QdrantClient: {e}. Falling back to local list storage.")
            self.client = None

    def add_chunks(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]) -> List[str]:
        """Adds text chunks and their embeddings to the vector store."""
        import uuid
        ids = []
        
        if self.client:
            try:
                points = []
                for idx, chunk in enumerate(chunks):
                    point_id = str(uuid.uuid4())
                    ids.append(point_id)
                    
                    payload = {
                        "subject": chunk.get("subject", "General"),
                        "chapter": str(chunk.get("chapter", "1")),
                        "topic": chunk.get("topic", "General"),
                        "page_number": int(chunk.get("page_number", 1)),
                        "document_id": str(chunk.get("document_id", "")),
                        "board": chunk.get("board", "NCERT"),
                        "class": str(chunk.get("class", "1")),
                        "difficulty": chunk.get("difficulty", "Easy"),
                        "chunk_text": chunk.get("chunk_text", ""),
                        "chunk_id": str(chunk.get("chunk_id", "")),
                        "curriculum_version": chunk.get("curriculum_version", "2026.1"),
                        "book_title": chunk.get("book_title", ""),
                        "chapter_name": chunk.get("chapter_name", "")
                    }
                    
                    points.append(
                        PointStruct(
                            id=point_id,
                            vector=vectors[idx],
                            payload=payload
                        )
                    )
                
                self.client.upsert(
                    collection_name=self.collection_name,
                    wait=True,
                    points=points
                )
                logger.info(f"Successfully added {len(points)} points to Qdrant collection {self.collection_name}.")
                return ids
            except Exception as e:
                logger.error(f"Failed Qdrant upsert: {e}. Attempting fallback...")
                
        # Heuristic local fallback
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid4())
            ids.append(point_id)
            self._memory_db.append({
                "id": point_id,
                "vector": vectors[idx],
                "payload": {
                    "subject": chunk.get("subject", "General"),
                    "chapter": str(chunk.get("chapter", "1")),
                    "topic": chunk.get("topic", "General"),
                    "page_number": int(chunk.get("page_number", 1)),
                    "document_id": str(chunk.get("document_id", "")),
                    "board": chunk.get("board", "NCERT"),
                    "class": str(chunk.get("class", "1")),
                    "difficulty": chunk.get("difficulty", "Easy"),
                    "chunk_text": chunk.get("chunk_text", ""),
                    "chunk_id": str(chunk.get("chunk_id", "")),
                    "curriculum_version": chunk.get("curriculum_version", "2026.1"),
                    "book_title": chunk.get("book_title", ""),
                    "chapter_name": chunk.get("chapter_name", "")
                }
            })
        logger.info(f"Successfully added {len(chunks)} points to in-memory fallback list.")
        return ids

    def search(self, vector: List[float], limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        """Searches vector index and returns similarity matches."""
        results = []
        
        if self.client:
            try:
                qdrant_filter = None
                if filter_dict:
                    conditions = []
                    for k, v in filter_dict.items():
                        conditions.append(
                            FieldCondition(
                                key=k,
                                match=MatchValue(value=v)
                            )
                        )
                    qdrant_filter = Filter(must=conditions)

                search_res = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    limit=limit,
                    query_filter=qdrant_filter
                ).points

                for point in search_res:
                    payload = point.payload or {}
                    results.append(
                        RetrievalResult(
                            chunk_id=payload.get("chunk_id", str(point.id)),
                            document_id=payload.get("document_id", ""),
                            chunk_text=payload.get("chunk_text", ""),
                            page_number=payload.get("page_number", 1),
                            chapter=payload.get("chapter", "1"),
                            topic=payload.get("topic", "General"),
                            score=float(point.score),
                            metadata=payload
                        )
                    )
                return results
            except Exception as e:
                logger.error(f"Error querying Qdrant: {e}. Searching in-memory fallback...")

        # Fallback in-memory cosine search
        for item in self._memory_db:
            payload = item["payload"]
            
            # Check filter conditions
            match = True
            if filter_dict:
                for k, v in filter_dict.items():
                    if str(payload.get(k)) != str(v):
                        match = False
                        break
            if not match:
                continue

            v1 = np.array(vector)
            v2 = np.array(item["vector"])
            norm_a = np.linalg.norm(v1)
            norm_b = np.linalg.norm(v2)
            sim = float(np.dot(v1, v2) / (norm_a * norm_b)) if norm_a > 0 and norm_b > 0 else 0.0

            results.append(
                RetrievalResult(
                    chunk_id=payload.get("chunk_id", item["id"]),
                    document_id=payload.get("document_id", ""),
                    chunk_text=payload.get("chunk_text", ""),
                    page_number=payload.get("page_number", 1),
                    chapter=payload.get("chapter", "1"),
                    topic=payload.get("topic", "General"),
                    score=sim,
                    metadata=payload
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
