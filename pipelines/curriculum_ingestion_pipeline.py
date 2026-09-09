import time
import os
from typing import Dict, Any, List, Optional
from loguru import logger

from ai_teacher_robot.rag.ingestion.pdf_loader import PDFLoader
from ai_teacher_robot.rag.ingestion.text_cleaner import TextCleaner
from ai_teacher_robot.rag.ingestion.metadata_extractor import MetadataExtractor
from ai_teacher_robot.rag.chunking.recursive_chunker import RecursiveChunker
from ai_teacher_robot.rag.chunking.curriculum_chunker import CurriculumChunker
from ai_teacher_robot.rag.chunking.chunk_validator import ChunkValidator
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from ai_teacher_robot.rag.embedding.embedding_cache import EmbeddingCache
from ai_teacher_robot.rag.vector_store.vector_factory import VectorStoreFactory

from ai_teacher_robot.repositories.curriculum_repository import CurriculumRepository
from ai_teacher_robot.repositories.source_repository import SourceRepository
from ai_teacher_robot.repositories.vector_repository import VectorRepository
from ai_teacher_robot.repositories.metadata_repository import MetadataRepository
from ai_teacher_robot.repositories.config_repository import ConfigRepository

from ai_teacher_robot.rag.schemas.document import CurriculumDocument, CurriculumSource
from ai_teacher_robot.rag.schemas.chunk import CurriculumChunk

class CurriculumIngestionPipeline:
    """Standalone pipeline that handles textbook PDF ingestion, cleaning, chunking, and vector index persistence."""
    def __init__(self) -> None:
        self.pdf_loader = PDFLoader()
        self.cleaner = TextCleaner()
        self.metadata_extractor = MetadataExtractor()
        
        self.recursive_chunker = RecursiveChunker(chunk_size=1000, chunk_overlap=200)
        self.curriculum_chunker = CurriculumChunker()
        self.validator = ChunkValidator()
        
        self.embedding_generator = EmbeddingGenerator()
        self.embedding_cache = EmbeddingCache()
        
        self.vector_store = VectorStoreFactory.get_vector_store(
            collection_name="curriculum_embeddings",
            dimension=self.embedding_generator.get_dimension()
        )
        
        self.doc_repo = CurriculumRepository()
        self.source_repo = SourceRepository()
        self.chunk_repo = VectorRepository()
        self.meta_repo = MetadataRepository()
        self.config_repo = ConfigRepository()

    async def ingest_pdf(self, pdf_path: str, uploaded_by: str = "Teacher", override_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Runs the entire ingestion loop on a textbook PDF.
        
        Returns the inserted document_id.
        """
        start_time = time.time()
        logger.info(f"Starting ingestion pipeline for: {pdf_path}")

        # 1. Load PDF & Extract raw text page by page
        raw_pages = self.pdf_loader.load_pdf(pdf_path)
        if not raw_pages:
            raise ValueError(f"No pages extracted from PDF: {pdf_path}")

        # 2. Clean text page by page
        cleaned_pages = []
        for page in raw_pages:
            cleaned_txt = self.cleaner.clean_text(page["plain_text"])
            cleaned_pages.append({
                "page_number": page["page_number"],
                "plain_text": cleaned_txt
            })

        # 3. Extract Metadata & PDF Table of Contents (TOC)
        from storage_service.services.pymupdf.pymupdf_service import PyMuPDFService
        from pathlib import Path
        pymupdf_svc = PyMuPDFService()
        toc_entries = []
        try:
            toc_entries = await pymupdf_svc.extract_toc(Path(pdf_path))
        except Exception as te:
            logger.warning(f"Could not extract TOC for {pdf_path}: {te}")

        first_page_txt = cleaned_pages[0]["plain_text"]
        filename = os.path.basename(pdf_path)
        heuristics = self.metadata_extractor.parse_filename_heuristics(filename, pdf_path)
        
        metadata = await self.metadata_extractor.extract_metadata_from_text(first_page_txt, heuristics)
        if override_metadata:
            metadata.update(override_metadata)

        # Extract TOC title if available and title is generic
        doc_title = metadata.get("title", "Chapter Title")
        if toc_entries and (doc_title == filename.replace(".pdf", "") or doc_title == "Chapter Title"):
            lvl1 = [e for e in toc_entries if e.get("level") == 1]
            if lvl1:
                doc_title = lvl1[0]["title"]

        # 4. Save CurriculumDocument
        version = metadata.get("curriculum_version") or (override_metadata or {}).get("curriculum_version") or "2026.1"
        doc = CurriculumDocument(
            title=doc_title,
            subject=metadata.get("subject", "General"),
            class_level=str(metadata.get("class", "1")),
            board=metadata.get("board", "NCERT"),
            chapter=str(metadata.get("chapter", "1")),
            uploaded_by=uploaded_by,
            curriculum_version=version,
            book_title=metadata.get("book_title"),
            toc=toc_entries
        )
        doc_id = await self.doc_repo.insert_document(doc)
        
        # 5. Save CurriculumSource
        source = CurriculumSource(
            id=doc.id,
            pdf_path=pdf_path,
            author=metadata.get("author"),
            edition=metadata.get("edition"),
            publisher=metadata.get("publisher")
        )
        await self.source_repo.insert_source(source)

        # 6. Chunking
        # First partition by curriculum topic boundaries
        curr_chunks = self.curriculum_chunker.chunk_document(cleaned_pages)
        
        # If topics are too large, sub-split recursively
        final_chunks = []
        for c in curr_chunks:
            txt = c["chunk_text"]
            if len(txt) > 1000:
                splits = self.recursive_chunker.split_text(txt)
                for split in splits:
                    final_chunks.append({
                        "chunk_text": split,
                        "page_number": c["page_number"],
                        "topic": c["topic"]
                    })
            else:
                final_chunks.append(c)

        # 7. Validate & filter chunks
        validated_chunks = self.validator.validate_and_filter_chunks(final_chunks)

        # 8. Embedding Generation & Store (MongoDB + Qdrant)
        chunk_objects = []
        vectors = []
        
        for idx, chunk in enumerate(validated_chunks):
            chunk_txt = chunk["chunk_text"]
            
            # Check embedding cache
            vector = self.embedding_cache.get_embedding(chunk_txt)
            if vector is None:
                vector = self.embedding_generator.generate_embedding(chunk_txt)
                self.embedding_cache.add_embedding(chunk_txt, vector)
                
            vectors.append(vector)
            
            # Prepare MongoDB chunk object
            chunk_obj = CurriculumChunk(
                document_id=doc.id,
                chunk_text=chunk_txt,
                page_number=chunk["page_number"],
                chapter=doc.chapter,
                topic=chunk["topic"]
            )
            chunk_objects.append(chunk_obj)

        # Insert chunks to MongoDB
        inserted_ids = await self.chunk_repo.insert_chunks(chunk_objects)
        
        # Associate point IDs with chunk embedding_id and upsert to Qdrant
        qdrant_chunks = []
        for idx, cid in enumerate(inserted_ids):
            chunk_objects[idx].id = cid
            chunk_objects[idx].embedding_id = cid
            
            qdrant_chunks.append({
                "chunk_id": cid,
                "document_id": str(doc.id),
                "chunk_text": chunk_objects[idx].chunk_text,
                "page_number": chunk_objects[idx].page_number,
                "chapter": doc.chapter,
                "topic": chunk_objects[idx].topic,
                "subject": doc.subject,
                "board": doc.board,
                "class": doc.class_level,
                "difficulty": metadata.get("difficulty", "Easy"),
                "curriculum_version": version,
                "book_title": doc.book_title or "",
                "chapter_name": doc.title
            })

        # Persist vectors and metadata payload to Qdrant
        self.vector_store.add_chunks(qdrant_chunks, vectors)

        # Save run statistics
        duration = time.time() - start_time
        run_stats = {
            "pdf_filename": filename,
            "document_id": doc_id,
            "total_pages": len(raw_pages),
            "chunks_count": len(validated_chunks),
            "execution_time_seconds": duration,
            "status": "Ready",
            "timestamp": time.time()
        }
        await self.meta_repo.save_run_metadata(f"run_{doc_id}", run_stats)
        
        # Set active version
        await self.config_repo.set_active_version(doc.subject, int(doc.class_level), version)
        
        logger.info(f"Ingestion pipeline completed successfully in {duration:.2f} seconds. Ingested {len(validated_chunks)} chunks.")
        return doc_id
