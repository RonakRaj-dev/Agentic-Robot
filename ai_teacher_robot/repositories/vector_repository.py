from typing import Optional, List, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.rag.schemas.chunk import CurriculumChunk
from ai_teacher_robot.repositories.db_client import db_manager

class VectorRepository:
    """Manages the curriculum_chunks (embedded under curriculum_documents) in MongoDB."""
    def __init__(self) -> None:
        self.collection_name = "curriculum_documents"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def insert_chunk(self, chunk: CurriculumChunk) -> str:
        col = await self._get_collection()
        chunk_dict = chunk.to_mongo()
        
        # Ensure chunk has an ID
        if not chunk.id:
            chunk.id = ObjectId()
            chunk_dict["id"] = chunk.id
            
        doc_id = chunk.document_id
        
        # Append chunk to the parent document's chunks list
        res = await col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$push": {"chunks": chunk_dict}}
        )
        inserted_id = str(chunk.id)
        logger.info(f"Embedded chunk {inserted_id} in document {doc_id} in MongoDB.")
        return inserted_id

    async def insert_chunks(self, chunks: List[CurriculumChunk]) -> List[str]:
        col = await self._get_collection()
        if not chunks:
            return []
            
        doc_id = chunks[0].document_id
        docs = []
        inserted_ids = []
        for c in chunks:
            if not c.id:
                c.id = ObjectId()
            inserted_ids.append(str(c.id))
            docs.append(c.to_mongo())
            
        res = await col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$push": {"chunks": {"$each": docs}}}
        )
        logger.info(f"Embedded {len(inserted_ids)} chunks in document {doc_id} in MongoDB.")
        return inserted_ids

    async def get_chunk(self, chunk_id: str) -> Optional[CurriculumChunk]:
        col = await self._get_collection()
        res = await col.find_one({"chunks.id": ObjectId(chunk_id)})
        if res:
            for ch_dict in res.get("chunks", []):
                if str(ch_dict.get("id")) == chunk_id:
                    ch_dict["document_id"] = res["_id"]
                    return CurriculumChunk.model_validate(ch_dict)
        return None

    async def get_chunks_for_document(self, doc_id: str) -> List[CurriculumChunk]:
        col = await self._get_collection()
        res = await col.find_one({"_id": ObjectId(doc_id)})
        if res and "chunks" in res:
            return [CurriculumChunk.model_validate(c) for c in res["chunks"]]
        return []

    async def delete_chunks_for_document(self, doc_id: str) -> bool:
        col = await self._get_collection()
        res = await col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"chunks": []}}
        )
        return res.modified_count > 0

