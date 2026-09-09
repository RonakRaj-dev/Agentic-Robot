from typing import Optional, List, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.rag.schemas.document import CurriculumDocument
from ai_teacher_robot.repositories.db_client import db_manager

import re

class CurriculumRepository:
    """Manages the curriculum_documents and BOOKS collections in MongoDB SiliconRag."""
    def __init__(self) -> None:
        self.collection_name = "curriculum_documents"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def ensure_indexes(self) -> None:
        """Startup DB reliability check: Auto-creates compound indices and text index for fast curriculum queries."""
        try:
            col = await self._get_collection()
            await col.create_index([("class", 1), ("subject", 1)])
            await col.create_index([("class_level", 1), ("subject", 1)])
            await col.create_index([
                ("chunks.chunk_text", "text"),
                ("title", "text"),
                ("chapter", "text")
            ], name="text_search_index")
            logger.info("Successfully validated MongoDB indices on 'curriculum_documents'.")
        except Exception as e:
            logger.warning(f"Note on MongoDB curriculum index validation: {e}")

    async def insert_document(self, doc: CurriculumDocument) -> str:
        if not doc.id:
            doc.id = ObjectId()
            
        col = await self._get_collection()
        doc_dict = doc.to_mongo()
        
        res = await col.insert_one(doc_dict)
        inserted_id = str(res.inserted_id)
        logger.info(f"Inserted document {inserted_id} into MongoDB.")
        return inserted_id

    async def get_document(self, doc_id: str) -> Optional[CurriculumDocument]:
        col = await self._get_collection()
        res = await col.find_one({"_id": ObjectId(doc_id)})
        if res:
            return CurriculumDocument.from_mongo(res)

        # Fallback to Schema v4 (BOOKS -> CHAPTERS -> CHUNKS)
        db = await db_manager.get_db()
        try:
            # 1. Search in CHAPTERS
            chapter_doc = await db["CHAPTERS"].find_one({"_id": ObjectId(doc_id)})
            if not chapter_doc:
                # Try finding by book_id / chapter_no
                chapter_doc = await db["CHAPTERS"].find_one({"book_id": doc_id})
            
            if chapter_doc:
                book_doc = await db["BOOKS"].find_one({"_id": ObjectId(chapter_doc["book_id"])})
                if book_doc:
                    # Retrieve chunks for this chapter
                    chunks_cursor = db["CHUNKS"].find({
                        "book_id": str(book_doc["_id"]),
                        "chapter_no": int(chapter_doc["chapter_no"])
                    })
                    chunks = []
                    async for ch_val in chunks_cursor:
                        chunks.append({
                            "id": ObjectId(ch_val.get("_id")) if ObjectId.is_valid(ch_val.get("_id")) else ObjectId(),
                            "chunk_text": ch_val.get("chunk_text", ""),
                            "page_number": int(ch_val.get("page_number", 1)),
                            "chapter": ch_val.get("chapter_name", ""),
                            "topic": ch_val.get("section", "General")
                        })
                    
                    return CurriculumDocument(
                        id=ObjectId(chapter_doc["_id"]),
                        title=chapter_doc.get("chapter_name", ""),
                        subject=book_doc.get("subject", "General"),
                        class_level=str(book_doc.get("class_no", 1)),
                        board=book_doc.get("board", "NCERT"),
                        chapter=f"Chapter {chapter_doc.get('chapter_no')}: {chapter_doc.get('chapter_name')}",
                        book_title=book_doc.get("title", ""),
                        chunks=chunks
                    )
        except Exception as e:
            logger.warning(f"Error resolving doc_id {doc_id} from Schema v4 collections: {e}")
            
        return None

    async def find_documents(self, filter_dict: Dict[str, Any]) -> List[CurriculumDocument]:
        col = await self._get_collection()
        query_filter = dict(filter_dict)
        if "_id" in query_filter and isinstance(query_filter["_id"], str):
            query_filter["_id"] = ObjectId(query_filter["_id"])

        subj_val = None
        if "subject" in query_filter and isinstance(query_filter["subject"], str):
            subj_val = query_filter.pop("subject")
            subj_pattern = re.escape(subj_val).replace('\\ ', '[ _]')
            pattern = f"^{subj_pattern}$"
            query_filter["subject"] = {"$regex": pattern, "$options": "i"}

        results = []
        try:
            cursor = col.find(query_filter)
            async for doc in cursor:
                results.append(CurriculumDocument.from_mongo(doc))
        except Exception as ce:
            logger.warning(f"Error querying curriculum_documents: {ce}")

        # Fallback / Direct check: Query Schema v4 collections (BOOKS -> CHAPTERS -> CHUNKS)
        db = await db_manager.get_db()
        books_col = db["BOOKS"]

        class_num = None
        for key in ["class", "class_level", "class_no"]:
            if key in filter_dict:
                val = filter_dict[key]
                match = re.search(r'\d+', str(val))
                if match:
                    class_num = int(match.group(0))
                    break
        
        if class_num is None and "$or" in filter_dict:
            for sub_filter in filter_dict["$or"]:
                for key in ["class", "class_level", "class_no"]:
                    if key in sub_filter:
                        val = sub_filter[key]
                        match = re.search(r'\d+', str(val))
                        if match:
                            class_num = int(match.group(0))
                            break
                if class_num is not None:
                    break

        books_query = {}
        if class_num is not None:
            books_query["class_no"] = class_num
        if subj_val:
            subj_pattern = re.escape(subj_val).replace('\\ ', '[ _]')
            books_query["subject"] = {"$regex": f"^{subj_pattern}$", "$options": "i"}

        try:
            b_cursor = books_col.find(books_query)
            async for book_doc in b_cursor:
                b_id = str(book_doc["_id"])
                
                # Retrieve all chapters for this book
                chapters_cursor = db["CHAPTERS"].find({"book_id": b_id})
                async for ch_doc in chapters_cursor:
                    ch_id = ch_doc["_id"]
                    ch_no = ch_doc["chapter_no"]
                    ch_name = ch_doc["chapter_name"]
                    
                    # Find all chunks for this chapter
                    chunks_cursor = db["CHUNKS"].find({
                        "book_id": b_id,
                        "chapter_no": ch_no
                    })
                    chunks = []
                    async for ch_val in chunks_cursor:
                        chunks.append({
                            "id": ch_val.get("_id") if isinstance(ch_val.get("_id"), ObjectId) else ObjectId(),
                            "chunk_text": ch_val.get("chunk_text", ""),
                            "page_number": int(ch_val.get("page_number", 1)),
                            "chapter": ch_val.get("chapter_name", ""),
                            "topic": ch_val.get("section", "General")
                        })
                        
                    curric_doc = CurriculumDocument(
                        id=ch_id,
                        title=ch_name,
                        subject=book_doc.get("subject", "General"),
                        class_level=str(book_doc.get("class_no", class_num or 1)),
                        board=book_doc.get("board", "NCERT"),
                        chapter=f"Chapter {ch_no}: {ch_name}",
                        book_title=book_doc.get("title", f"Class {book_doc.get('class_no')} {book_doc.get('subject')}"),
                        chunks=chunks
                    )
                    results.append(curric_doc)
        except Exception as err:
            logger.warning(f"Error querying BOOKS/CHAPTERS/CHUNKS collections in find_documents: {err}")

        return results

    async def delete_document(self, doc_id: str) -> bool:
        col = await self._get_collection()
        res = await col.delete_one({"_id": ObjectId(doc_id)})
        return res.deleted_count > 0

    async def get_subjects_by_class(self, class_level: str | int) -> List[str]:
        col = await self._get_collection()
        
        query_filter = {}
        if str(class_level).isdigit():
            query_filter = {
                "$or": [
                    {"class": str(class_level)},
                    {"class": int(class_level)}
                ]
            }
        else:
            query_filter = {"class": str(class_level)}
            
        raw_subjects = await col.distinct("subject", query_filter)

        # Also fetch subjects from BOOKS collection in SiliconRag
        try:
            db = await db_manager.get_db()
            books_col = db["BOOKS"]
            class_num = int(re.search(r'\d+', str(class_level)).group(0)) if re.search(r'\d+', str(class_level)) else 1
            books_subjects = await books_col.distinct("subject", {"class_no": class_num})
            if books_subjects:
                raw_subjects.extend(books_subjects)
        except Exception as err:
            logger.warning(f"Error fetching distinct subjects from BOOKS collection: {err}")
        
        seen_keys = set()
        cleaned_subjects = []
        for s in raw_subjects:
            if not s or not isinstance(s, str):
                continue
            normalized = " ".join(s.replace("_", " ").split()).title()
            key = normalized.lower()
            if key not in seen_keys:
                seen_keys.add(key)
                cleaned_subjects.append(normalized)

        return sorted(cleaned_subjects)
