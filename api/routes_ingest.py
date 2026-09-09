import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form
from pipelines.curriculum_ingestion_pipeline import CurriculumIngestionPipeline

router = APIRouter()
pipeline = CurriculumIngestionPipeline()

@router.post("/ingest")
async def ingest_endpoint(
    file: UploadFile = File(...),
    grade: int = Form(...),
    subject: str = Form(...),
    chapter: str = Form(...),
    curriculum_version: str = Form(...)
):
    try:
        # 1. Ensure raw curriculum directory exists
        save_dir = f"data/curriculum_raw/{grade}/{subject}"
        os.makedirs(save_dir, exist_ok=True)
        
        # 2. Save file locally
        file_path = os.path.join(save_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Call ingestion pipeline
        override_metadata = {
            "subject": subject,
            "class": str(grade),
            "chapter": str(chapter),
            "curriculum_version": curriculum_version,
            "title": file.filename.replace(".pdf", "").replace(".doc", "").replace(".docx", "")
        }
        
        doc_id = await pipeline.ingest_pdf(
            pdf_path=file_path,
            uploaded_by="Admin-API",
            override_metadata=override_metadata
        )
        
        # 4. Count chunks created
        chunks = await pipeline.chunk_repo.get_chunks_for_document(doc_id)
        
        return {
            "chunks_created": len(chunks),
            "curriculum_version": curriculum_version,
            "status": "success"
        }
    except Exception as e:
        return {
            "chunks_created": 0,
            "curriculum_version": curriculum_version,
            "status": "error",
            "error_detail": str(e)
        }
