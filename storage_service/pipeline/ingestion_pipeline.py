"""Complete PDF ingestion pipeline — PyMuPDF only, schema v3.

Pipeline flow (catalog-driven):

    newestbooks.json  →  Catalog Import  →  BOOKS collection
                                                    ↓
    For each chapter PDF:
        find existing book by pdf_filename → ingest_chapter()
        (NO create_book() — appends to existing book's chapter)
            ↓
        Upload full chapter PDF to MinIO (StorageService.upload_pdf)
        Save PDF reference on EmbeddedChapter
            ↓
        PyMuPDF text extraction (page-by-page, streaming)
            ↓
        For each page:
            • Render page as PNG using PyMuPDF
            • Upload page image to MinIO (StorageService.upload_page_image)
            • Accumulate PAGE_IMAGE object dicts in memory
            ↓
        Batch-persist all page objects in a single $push + $each
        Finalize chapter (processed_pages + page_end in one write)

Key design — schema v3:
  * Each chapter stores its full PDF reference directly
    (pdf_object_key, pdf_bucket_name, pdf_size_bytes).
  * objects[] contains PAGE_IMAGE entries — one per page.
  * Each PAGE_IMAGE object carries both MinIO storage reference AND
    extracted text metadata (plain_text, word_count, token_count,
    extraction_method).
  * processed_pages counter tracks processed page count per chapter.
  * total_pages = sum of all pages across ALL chapter PDFs.

.. versionchanged:: v7
    ``pdf_object_url`` is no longer written (it was already deprecated
    in v6).  Access URLs are built on demand via
    :meth:`IStorageService.get_public_url`.  Presigned URL generation
    has been removed entirely.

Modularisation:
  The per-page loop lives in :mod:`pipeline.page_processing`.
  The chapter-PDF upload lives in :mod:`pipeline.chapter_ingestion`.
  Book/chapter walking helpers live in :mod:`pipeline.book_walking`.
  This module is the thin orchestrator that wires them together.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import get_settings
from core.exceptions import (
    ExtractionError,
    MetadataExtractionError,
    PDFCorruptedError,
    PDFValidationError,
)
from interfaces.book_service import IBookService
from interfaces.pymupdf_service import IPyMuPDFService
from interfaces.storage_service import IStorageService
from interfaces.progress_callback import IProgressCallback
from models.ingestion_input import IngestionInput
from models.ingestion_result import (
    IngestionErrorRecord,
    IngestionResult,
    PipelineStatus,
)
from pipeline.chapter_ingestion import upload_chapter_pdf_and_attach
from pipeline.page_processing import store_pages_as_images
from utils.pdf_utils import (
    extract_pdf_metadata,
    validate_pdf,
)
from utils.progress_utils import LoggingProgressCallback
from utils.retry_utils import with_minio_retry, with_mongo_retry, with_extraction_retry

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Production-ready PDF ingestion pipeline — PyMuPDF only.

    Each chapter PDF is processed as follows:
      1. The full chapter PDF is uploaded to MinIO and its reference is
         saved directly on the EmbeddedChapter.
      2. PyMuPDF extracts text from each page.
      3. Each page is rendered as a PNG image and uploaded to MinIO.
      4. The PAGE_IMAGE object dicts are accumulated in memory and
         persisted in a single batched ``$push + $each`` write.
      5. ``processed_pages`` and ``page_end`` are stamped in one write.

    ``total_pages`` on the Book document accumulates across all chapter
    PDFs — it represents the total number of pages in the entire book.
    """

    def __init__(
        self,
        storage_service: IStorageService,
        book_service: IBookService,
        pymupdf_service: IPyMuPDFService,
        progress_callback: Optional[IProgressCallback] = None,
        config: Optional[Any] = None,
    ) -> None:
        self.storage = storage_service
        self.books = book_service
        self.pymupdf = pymupdf_service
        self.progress = progress_callback or LoggingProgressCallback()
        # ``config`` is retained for backwards compatibility but no
        # longer read — the pipeline gets bucket names from the
        # StorageService's StorageRef, not from settings.
        self.config = config or get_settings()
        logger.info("IngestionPipeline initialised (PyMuPDF engine)")

    # ── catalog-driven chapter ingestion (NO book creation) ───────────

    async def ingest_chapter(
        self,
        pdf_path: Path,
        book_id: str,
        chapter_no: int,
    ) -> IngestionResult:
        """Ingest a single chapter PDF into an EXISTING Book document.

        This is the catalog-driven entry point. It does NOT call
        ``create_book()`` — the Book must already exist from catalog
        import.  It locates the chapter by ``chapter_no`` within the
        existing book, then:

          1. Uploads the full chapter PDF to MinIO and saves the
             reference on the chapter.
          2. Extracts text page-by-page via PyMuPDF.
          3. Renders each page as a PNG image and uploads to MinIO.
          4. Batch-persists all PAGE_IMAGE objects in a single
             ``$push + $each`` write.
          5. Finalises the chapter (processed_pages + page_end in one
             write) and adjusts book.total_pages by the delta.

        Re-ingestion is idempotent: existing page objects are cleared
        before re-storing, and total_pages is adjusted by the delta
        (= new_page_count - previous_processed_pages) so it doesn't
        double-count.
        """
        start_time = time.time()
        result = IngestionResult(pipeline_status=PipelineStatus.IN_PROGRESS)
        result.book_id = book_id

        try:
            # ── Stage 1: PDF validation ──────────────────────────────
            await self.progress.on_stage_start(
                "pdf_validation", "Validating chapter PDF"
            )
            validate_pdf(pdf_path)
            await self.progress.on_stage_complete("pdf_validation", "PDF valid")

            # ── Stage 2: Metadata extraction ─────────────────────────
            await self.progress.on_stage_start(
                "metadata_extraction", "Extracting metadata"
            )
            pdf_metadata = extract_pdf_metadata(pdf_path)
            result.metadata = pdf_metadata
            result.total_pages = pdf_metadata["page_count"]
            await self.progress.on_stage_complete(
                "metadata_extraction", f"{pdf_metadata['page_count']} pages"
            )

            # ── Stage 3: Upload chapter PDF + look up existing state ──
            await self.progress.on_stage_start(
                "pdf_upload", "Uploading chapter PDF to MinIO"
            )
            chapter_id, previous_processed_pages = await self._upload_chapter_pdf(
                pdf_path=pdf_path,
                book_id=book_id,
                chapter_no=chapter_no,
            )
            await self.progress.on_stage_complete(
                "pdf_upload", "Chapter PDF uploaded"
            )

            # ── Stage 3b: Adjust book total_pages by the delta ──────
            await self.books.update_book_total_pages(
                book_id=book_id,
                total_pages=pdf_metadata["page_count"] - previous_processed_pages,
            )

            # ── Stage 3c: Clear existing page objects on re-ingest ─
            if previous_processed_pages > 0:
                await self.books.clear_chapter_objects(
                    book_id=book_id, chapter_id=chapter_id,
                )

            # ── Stage 4: PyMuPDF text extraction ────────────────────
            await self.progress.on_stage_start(
                "pymupdf_processing",
                "Running PyMuPDF text extraction",
                pdf_metadata["page_count"],
            )
            extraction_result = await self._run_pymupdf(pdf_path, book_id)
            await self.progress.on_stage_complete(
                "pymupdf_processing",
                f"PyMuPDF done — {extraction_result['total_pages']} pages",
            )

            # ── Stage 5: Render pages, upload, batch-persist ─────────
            await self.progress.on_stage_start(
                "page_processing",
                "Rendering pages and storing in MongoDB",
                extraction_result["total_pages"],
            )
            await store_pages_as_images(
                pdf_path=pdf_path,
                book_id=book_id,
                chapter_id=chapter_id,
                chapter_no=chapter_no,
                extraction_result=extraction_result,
                result=result,
                books=self.books,
                storage=self.storage,
                progress=self.progress,
            )
            await self.progress.on_stage_complete(
                "page_processing",
                f"{result.pages_processed}/{result.total_pages} done",
            )

            result.processing_time_seconds = round(time.time() - start_time, 2)
            result.mark_completed()
            return result

        except (PDFValidationError, PDFCorruptedError, MetadataExtractionError) as e:
            result.add_error(
                IngestionErrorRecord(
                    stage=e.stage, error_type=type(e).__name__, error_message=str(e)
                )
            )
            result.pipeline_status = PipelineStatus.FAILED
            result.processing_time_seconds = round(time.time() - start_time, 2)
            return result
        except Exception as e:
            logger.exception("ingest_chapter failed")
            result.add_error(
                IngestionErrorRecord(
                    stage="pipeline", error_type=type(e).__name__, error_message=str(e)
                )
            )
            result.pipeline_status = PipelineStatus.FAILED
            result.processing_time_seconds = round(time.time() - start_time, 2)
            return result

    # ── chapter PDF upload (delegates to pipeline.chapter_ingestion) ─

    @with_minio_retry
    async def _upload_chapter_pdf(
        self,
        pdf_path: Path,
        book_id: str,
        chapter_no: int,
    ) -> tuple[str, int]:
        """Upload the chapter PDF and save its reference on the chapter.

        Delegates to :func:`pipeline.chapter_ingestion.upload_chapter_pdf_and_attach`.
        Returns ``(chapter_id, previous_processed_pages)``.
        """
        return await upload_chapter_pdf_and_attach(
            pdf_path=pdf_path,
            book_id=book_id,
            chapter_no=chapter_no,
            books=self.books,
            storage=self.storage,
        )

    # ── PyMuPDF processing ─────────────────────────────────────────────

    @with_extraction_retry
    async def _run_pymupdf(
        self, pdf_path: Path, book_id: str
    ) -> Dict[str, Any]:
        """Run PyMuPDF text extraction on the PDF."""
        try:
            return await self.pymupdf.extract_pages(
                pdf_path=pdf_path,
                book_id=book_id,
            )
        except Exception as exc:
            raise ExtractionError(
                f"PyMuPDF processing failed: {exc}"
            ) from exc

    # ── legacy single-PDF ingestion (kept for backwards compat) ──────

    async def ingest(self, input_data: IngestionInput) -> IngestionResult:
        """Legacy single-PDF ingestion entry point.

        Creates a new Book document from a single PDF.  This is kept for
        backwards compatibility with the original CLI (``ingest.py``).
        For catalog-driven ingestion, use ``ingest_chapter()`` instead.
        """
        start_time = time.time()
        result = IngestionResult(pipeline_status=PipelineStatus.IN_PROGRESS)
        try:
            # Stage 1: PDF validation
            await self.progress.on_stage_start("pdf_validation", "Validating PDF")
            validate_pdf(input_data.pdf_path)
            await self.progress.on_stage_complete("pdf_validation", "PDF valid")

            # Stage 2: Metadata extraction
            await self.progress.on_stage_start(
                "metadata_extraction", "Extracting metadata"
            )
            pdf_metadata = extract_pdf_metadata(input_data.pdf_path)
            result.metadata = pdf_metadata
            result.total_pages = pdf_metadata["page_count"]
            await self.progress.on_stage_complete(
                "metadata_extraction", f"{pdf_metadata['page_count']} pages"
            )

            # Stage 3: Upload source PDF to MinIO
            await self.progress.on_stage_start("pdf_upload", "Uploading PDF")
            pdf_storage_ref = await self._upload_pdf_to_storage(input_data)
            # v7: store the structured ref, not a URL.  ``pdf_storage_ref``
            # is a StorageRef carrying bucket_name + object_key.  The
            # legacy ``pdf_storage_url`` metadata key is retained (as
            # the object_key) for backward compat with callers that
            # introspect the result, but no URL is persisted.
            result.metadata["pdf_storage_ref"] = {
                "bucket": pdf_storage_ref.bucket_name,
                "object_key": pdf_storage_ref.object_key,
            }
            
            # Stage 4: Find or Create Book document
            await self.progress.on_stage_start("book_creation", "Creating Book")
            
            # Determine class_no from class_level
            import re
            class_digits = re.search(r'\d+', str(input_data.class_level))
            class_no = int(class_digits.group(0)) if class_digits else 1
            
            # Extract chapter_no from pdf path/filename
            filename = input_data.pdf_path.name.lower()
            chapter_no = 1
            if "chapter_no" in input_data.processing_options:
                chapter_no = int(input_data.processing_options["chapter_no"])
            else:
                ncert_match = re.match(r'^[a-z]{4}(\d)(\d{2})\.pdf$', filename)
                if ncert_match:
                    chapter_no = int(ncert_match.group(2))
                else:
                    chapter_match = re.search(r'chapter[_\-\s]*(\d+)', filename)
                    if chapter_match:
                        chapter_no = int(chapter_match.group(1))
                    else:
                        end_digits = re.search(r'(\d+)\.pdf$', filename)
                        if end_digits:
                            chapter_no = int(end_digits.group(1))
            
            # Check if there is an existing Book document with matching board/class/subject
            book_id = await self.books.get_book_by_code(
                class_no=class_no,
                subject=input_data.subject,
                title=None,
                board=input_data.board,
            )
            if not book_id:
                # Fallback check for alternate subject spelling (e.g. Maths vs Mathematics)
                alt_subj = "Mathematics" if input_data.subject == "Maths" else ("Maths" if input_data.subject == "Mathematics" else None)
                if alt_subj:
                    book_id = await self.books.get_book_by_code(
                        class_no=class_no,
                        subject=alt_subj,
                        title=None,
                        board=input_data.board,
                    )
            
            is_new_book = False
            previous_processed_pages = 0
            chapter_id = None
            
            if not book_id:
                is_new_book = True
                result.pdf_media_asset_id = f"pdf::{input_data.pdf_path.name}"
                book_id = await self._create_book(
                    input_data, pdf_metadata, result.pdf_media_asset_id
                )
            else:
                # Inspect book to see if chapter already exists (re-ingestion idempotency)
                existing_book = await self.books.get_book(book_id)
                if existing_book:
                    ch_list = existing_book.chapters if hasattr(existing_book, "chapters") else existing_book.get("chapters", [])
                    for ch in ch_list:
                        ch_no = ch.chapter_no if hasattr(ch, "chapter_no") else ch.get("chapter_no")
                        if ch_no == chapter_no:
                            chapter_id = str(ch.id if hasattr(ch, "id") else ch.get("id"))
                            previous_processed_pages = ch.processed_pages if hasattr(ch, "processed_pages") else ch.get("processed_pages", 0)
                            break
            
            result.book_id = book_id
            
            if is_new_book:
                await self.books.attach_source_pdf(
                    book_id=book_id,
                    file_path=input_data.pdf_path,
                    metadata={
                        "original_filename": input_data.pdf_path.name,
                        "file_size": input_data.pdf_path.stat().st_size,
                        "board": input_data.board,
                        "class_level": input_data.class_level,
                        "subject": input_data.subject,
                    },
                    bucket_name=pdf_storage_ref.bucket_name,
                    object_key=pdf_storage_ref.object_key,
                )
            await self.progress.on_stage_complete("book_creation", f"Book: {book_id}")

            # Stage 5: Create or Add Chapter
            await self.progress.on_stage_start(
                "chapter_creation", "Creating Chapter"
            )
            if not chapter_id:
                chapter_id = await self.books.add_chapter(
                    book_id=book_id,
                    chapter_no=chapter_no,
                    title=input_data.book_metadata.title,
                    page_start=1,
                    page_end=pdf_metadata["page_count"],
                )
            result.chapter_ids = [chapter_id]
            await self.progress.on_stage_complete(
                "chapter_creation", f"Chapter {chapter_no}: {chapter_id}"
            )

            # Stage 5b: Adjust book total_pages by delta and clear old page objects if re-ingested
            if not is_new_book:
                delta = pdf_metadata["page_count"] - previous_processed_pages
                if delta != 0:
                    await self.books.update_book_total_pages(
                        book_id=book_id,
                        total_pages=delta,
                    )
            if previous_processed_pages > 0:
                await self.books.clear_chapter_objects(
                    book_id=book_id,
                    chapter_id=chapter_id,
                )

            # Stage 6: Upload chapter PDF reference
            await self.progress.on_stage_start(
                "chapter_pdf_upload", "Uploading chapter PDF"
            )
            await self.storage.upload_file(
                bucket_name=pdf_storage_ref.bucket_name,
                object_name=f"books/{book_id}/chapters/{chapter_no}/chapter.pdf",
                file_path=input_data.pdf_path,
                content_type="application/pdf",
            )
            await self.books.update_chapter_pdf_ref(
                book_id=book_id,
                chapter_id=chapter_id,
                pdf_bucket_name=pdf_storage_ref.bucket_name,
                pdf_object_key=f"books/{book_id}/chapters/{chapter_no}/chapter.pdf",
                pdf_size_bytes=input_data.pdf_path.stat().st_size,
            )
            await self.progress.on_stage_complete(
                "chapter_pdf_upload", "Chapter PDF uploaded"
            )

            # Stage 7: PyMuPDF extraction
            await self.progress.on_stage_start(
                "pymupdf_processing",
                "Running PyMuPDF text extraction",
                pdf_metadata["page_count"],
            )
            extraction_result = await self._run_pymupdf(input_data.pdf_path, book_id)
            await self.progress.on_stage_complete(
                "pymupdf_processing",
                f"PyMuPDF done — {extraction_result['total_pages']} pages",
            )

            # Stage 8: Render pages as PNGs and store
            await self.progress.on_stage_start(
                "page_processing",
                "Rendering pages and storing in MongoDB",
                extraction_result["total_pages"],
            )
            await store_pages_as_images(
                pdf_path=input_data.pdf_path,
                book_id=book_id,
                chapter_id=chapter_id,
                chapter_no=chapter_no,
                extraction_result=extraction_result,
                result=result,
                books=self.books,
                storage=self.storage,
                progress=self.progress,
            )
            await self.progress.on_stage_complete(
                "page_processing",
                f"{result.pages_processed}/{result.total_pages} done",
            )

            result.processing_time_seconds = round(time.time() - start_time, 2)
            result.mark_completed()
            return result

        except (PDFValidationError, PDFCorruptedError, MetadataExtractionError) as e:
            result.add_error(
                IngestionErrorRecord(
                    stage=e.stage, error_type=type(e).__name__, error_message=str(e)
                )
            )
            result.pipeline_status = PipelineStatus.FAILED
            result.processing_time_seconds = round(time.time() - start_time, 2)
            return result
        except Exception as e:
            logger.exception("ingest failed")
            result.add_error(
                IngestionErrorRecord(
                    stage="pipeline", error_type=type(e).__name__, error_message=str(e)
                )
            )
            result.pipeline_status = PipelineStatus.FAILED
            result.processing_time_seconds = round(time.time() - start_time, 2)
            return result

    @with_minio_retry
    async def _upload_pdf_to_storage(self, input_data: IngestionInput) -> "StorageRef":
        """Upload the book-level source PDF (legacy path).

        Uses the low-level ``upload_file`` because there's no business
        operation for book-level source PDFs (only chapter PDFs have
        one).  The bucket name is read from settings here because this
        is the StorageService's own concern — but note the pipeline
        does NOT read ``minio_bucket_pdf`` for chapter PDFs (those go
        through ``upload_pdf`` which returns a StorageRef).

        .. versionchanged:: v7
            Returns a :class:`StorageRef` (no ``url`` field — removed
            in v7) instead of a URL string.  Callers persist the
            structured ``(bucket_name, object_key)`` fields — never a
            URL.  Access URLs are built on demand via
            :meth:`IStorageService.get_public_url`.
        """
        from interfaces.storage_service import StorageRef
        object_name = (
            f"books/{input_data.board}/{input_data.class_level}/"
            f"{input_data.subject}/{input_data.pdf_path.name}"
        )
        # upload_file returns a public URL; we discard it and construct
        # a StorageRef carrying bucket + key only.
        await self.storage.upload_file(
            bucket_name=self.config.minio_bucket_pdf,
            object_name=object_name,
            file_path=input_data.pdf_path,
            content_type="application/pdf",
        )
        return StorageRef(
            bucket_name=self.config.minio_bucket_pdf,
            object_key=object_name,
        )

    @with_mongo_retry
    async def _create_book(
        self,
        input_data: IngestionInput,
        pdf_metadata: Dict[str, Any],
        pdf_asset_id: str,
    ) -> str:
        merged_metadata = {
            "extracted_title": pdf_metadata.get("title"),
            "extracted_author": pdf_metadata.get("author"),
            "publisher": input_data.book_metadata.publisher
            or pdf_metadata.get("producer"),
            **input_data.book_metadata.metadata,
        }
        return await self.books.create_book(
            title=input_data.book_metadata.metadata.get("book_title") or input_data.book_metadata.title,
            class_level=input_data.class_level,
            subject=input_data.subject,
            language=input_data.language,
            board=input_data.board,
            metadata=merged_metadata,
            pdf_asset_id=pdf_asset_id,
            total_pages=pdf_metadata["page_count"],
        )
