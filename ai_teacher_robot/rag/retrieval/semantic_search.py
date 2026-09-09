from typing import List, Dict, Any, Optional
from ai_teacher_robot.rag.vector_store.vector_factory import VectorStoreFactory
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult

class SemanticSearch:
    """Executes semantic vector searches against the configured vector store."""
    def __init__(self, collection_name: str = "curriculum_embeddings", dimension: int = 384) -> None:
        self.vector_store = VectorStoreFactory.get_vector_store(
            collection_name=collection_name, 
            dimension=dimension
        )

    async def search(self, vector: List[float], limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        return self.vector_store.search(vector=vector, limit=limit, filter_dict=filters)
