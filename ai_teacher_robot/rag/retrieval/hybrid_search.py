from typing import List, Dict, Any, Optional
from ai_teacher_robot.rag.retrieval.semantic_search import SemanticSearch
from ai_teacher_robot.rag.retrieval.bm25_search import BM25Search
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult


class HybridSearch:
    """Executes dual-query hybrid retrieval combining Qdrant dense vector search and MongoDB BM25 sparse keyword search."""

    def __init__(self, collection_name: str = "curriculum_embeddings", dimension: int = 384) -> None:
        self.semantic_search = SemanticSearch(collection_name, dimension)
        self.bm25_search = BM25Search()

    async def search(
        self,
        vector: List[float],
        bm25_query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Runs dense vector search with query vector and BM25 search with keyword query, merging via RRF (k=60)."""
        # 1. Run both searches
        semantic_res = await self.semantic_search.search(vector, limit=limit, filters=filters)
        bm25_res = await self.bm25_search.search(bm25_query, limit=limit, filters=filters)

        # 2. Reciprocal Rank Fusion (RRF k=60)
        rrf_scores: Dict[str, float] = {}
        result_objects: Dict[str, RetrievalResult] = {}

        # Semantic vector ranks
        for rank, item in enumerate(semantic_res, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            result_objects[cid] = item

        # BM25 keyword ranks
        for rank, item in enumerate(bm25_res, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            if cid not in result_objects:
                result_objects[cid] = item

        # Assign RRF scores
        combined: List[RetrievalResult] = []
        for cid, score in rrf_scores.items():
            res_obj = result_objects[cid]
            res_obj.score = score
            combined.append(res_obj)

        combined.sort(key=lambda x: x.score, reverse=True)
        return combined[:limit]
