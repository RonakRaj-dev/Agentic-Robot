from typing import List, Dict, Any, Optional
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.vector_repository import VectorRepository
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult

class BM25Search:
    """Executes keyword-based text searches using MongoDB full-text indexes or local fallback matchers."""
    def __init__(self) -> None:
        self.repo = VectorRepository()

    async def search(self, query: str, limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[RetrievalResult]:
        import re
        col = await self.repo._get_collection()
        results = []

        if col is not None:
            try:
                # 1. Match documents containing keywords via text search
                match_stage = {"$text": {"$search": query}}
                if filters:
                    for k, v in filters.items():
                        if k == "document_id":
                            match_stage["_id"] = ObjectId(v)
                        elif k == "class":
                            match_stage["class_level"] = str(v)
                        elif k == "subject" and isinstance(v, str):
                            subj_pattern = re.escape(v).replace('\\ ', '[ _]')
                            pattern = f"^{subj_pattern}$"
                            match_stage["subject"] = {"$regex": pattern, "$options": "i"}
                        else:
                            match_stage[k] = v

                # 2. Aggregation pipeline to unwind chunks and match text score
                pipeline = [
                    {"$match": match_stage},
                    {"$project": {
                        "title": 1,
                        "subject": 1,
                        "class_level": 1,
                        "board": 1,
                        "chapter": 1,
                        "chunks": 1,
                        "score": {"$meta": "textScore"}
                    }},
                    {"$unwind": "$chunks"}
                ]
                
                # Filter unwound chunks to only those matching query terms to keep precision high
                words = [w for w in query.split() if len(w) > 2]
                if words:
                    regex_str = "|".join(re.escape(w) for w in words)
                    pipeline.append({"$match": {"chunks.chunk_text": {"$regex": regex_str, "$options": "i"}}})
                    
                pipeline.extend([
                    {"$project": {
                        "_id": "$chunks.id",
                        "document_id": "$_id",
                        "chunk_text": "$chunks.chunk_text",
                        "page_number": "$chunks.page_number",
                        "chapter": "$chapter",
                        "topic": "$chunks.topic",
                        "score": "$score"
                    }},
                    {"$sort": {"score": -1}},
                    {"$limit": limit}
                ])

                cursor = col.aggregate(pipeline)
                async for doc in cursor:
                    results.append(
                        RetrievalResult(
                            chunk_id=str(doc["_id"]),
                            document_id=str(doc["document_id"]),
                            chunk_text=doc["chunk_text"],
                            page_number=doc["page_number"],
                            chapter=doc["chapter"],
                            topic=doc.get("topic", "General"),
                            score=doc.get("score", 1.0),
                            metadata=doc
                        )
                    )
                return results
            except Exception as e:
                logger.warning(f"MongoDB text search failed (maybe index not built yet?): {e}. Running local keyword matcher.")

        # Heuristic local match fallback
        query_words = set(query.lower().split())
        local_results = []
        
        # Load all chunks for document/filter if possible
        all_chunks = []
        if filters and "document_id" in filters:
            all_chunks = await self.repo.get_chunks_for_document(filters["document_id"])
        else:
            if col is not None:
                cursor = col.find({})
                async for doc in cursor:
                    for ch in doc.get("chunks", []):
                        ch_dict = dict(ch)
                        ch_dict["document_id"] = doc["_id"]
                        all_chunks.append(ch_dict)
            else:
                for doc_dict in self.repo._local_storage.values():
                    all_chunks.append(doc_dict)

        for chunk in all_chunks:
            # Handle chunk dictionary or pydantic model
            text = chunk.get("chunk_text", "").lower() if isinstance(chunk, dict) else chunk.chunk_text.lower()
            
            # Match filter
            match = True
            if filters:
                for k, v in filters.items():
                    val = chunk.get(k) if isinstance(chunk, dict) else getattr(chunk, k, None)
                    if str(val) != str(v):
                        match = False
                        break
            if not match:
                continue

            words = set(text.split())
            intersection = query_words.intersection(words)
            if intersection:
                score = len(intersection) / len(query_words)
                
                cid = str(chunk.get("_id") if isinstance(chunk, dict) else chunk.id)
                did = str(chunk.get("document_id") if isinstance(chunk, dict) else chunk.document_id)
                ctxt = chunk.get("chunk_text") if isinstance(chunk, dict) else chunk.chunk_text
                pno = chunk.get("page_number") if isinstance(chunk, dict) else chunk.page_number
                ch = chunk.get("chapter") if isinstance(chunk, dict) else chunk.chapter
                top = chunk.get("topic") if isinstance(chunk, dict) else chunk.topic
                
                local_results.append(
                    RetrievalResult(
                        chunk_id=cid,
                        document_id=did,
                        chunk_text=ctxt,
                        page_number=pno,
                        chapter=ch,
                        topic=top,
                        score=score,
                        metadata={}
                    )
                )

        # Sort descending by score
        local_results.sort(key=lambda x: x.score, reverse=True)
        return local_results[:limit]
