"""Page processing — render, upload, and batch-persist page images.

This module is the single home for the per-page loop that used to
live inside ``IngestionPipeline._store_pages_as_images``.  Splitting
it out lets the orchestrator (``IngestionPipeline``) stay thin and
makes the batching strategy explicit:

  * Pages are rendered to PNG bytes in memory.
  * Each PNG is uploaded to MinIO via ``storage.upload_page_image``
    (returns a :class:`StorageRef` — no settings lookup needed).
  * The resulting PAGE_IMAGE objects are accumulated in a list and
    persisted to ``chapter.objects[]`` in a SINGLE batched
    ``$push + $each`` write via ``books.append_processed_pages``.
  * Finally, ``processed_pages`` and ``page_end`` are stamped in one
    write via ``books.finalize_chapter_ingestion``.

For a 144-page chapter this reduces MongoDB round trips from
~146 (1 per page + 2 finalisers) to **2** (1 batch append + 1
finalise).  Failed pages are still recorded individually in the
``IngestionResult`` so the caller can see which pages failed.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from core.exceptions import MongoWriteError
from db.models.embedded import ExtractionMethod
from interfaces.book_service import IBookService
from interfaces.progress_callback import IProgressCallback
from interfaces.storage_service import IStorageService
from models.ingestion_result import (
    IngestionErrorRecord,
    IngestionResult,
    PageProcessingResult,
)

logger = logging.getLogger(__name__)

# Render PNGs at 150 DPI — matches the previous hardcoded default.
_RENDER_DPI = 150


async def store_pages_as_images(
    pdf_path: Path,
    book_id: str,
    chapter_id: str,
    chapter_no: int,
    extraction_result: Dict[str, Any],
    result: IngestionResult,
    books: IBookService,
    storage: IStorageService,
    progress: IProgressCallback,
) -> None:
    """Render each page to PNG, upload to MinIO, batch-persist to Mongo.

    This function replaces the previous
    ``IngestionPipeline._store_pages_as_images`` method.  The
    batching strategy is documented in the module docstring.
    """
    total = result.total_pages
    pages: List[Dict[str, Any]] = extraction_result["pages"]

    import fitz
    doc = None
    # Accumulate successful page dicts for the single batched $push.
    # Each entry pairs the page dict (for the batched write) with the
    # index of the corresponding PageProcessingResult (so we can
    # back-fill the object_id after the batch write returns).
    batch: List[Dict[str, Any]] = []
    batch_result_indices: List[int] = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_data in pages:
            page_number = page_data["page_number"]
            page_start = time.time()

            try:
                await progress.on_progress(
                    "page_processing",
                    page_number,
                    total,
                    f"Page {page_number} - Rendering & Storing",
                )

                # 1) Render page as PNG.
                png_bytes = _render_page_as_png(doc, page_number - 1)

                # 2) Upload PNG to MinIO via the StorageService business
                #    operation.  Returns a StorageRef carrying bucket
                #    name and object key — no settings lookup.
                #    v7: ``ref`` carries ``(bucket_name, object_key)``
                #    only; no URL is stored.  Callers that need an
                #    access URL request one on demand via
                #    ``storage.get_public_url``.
                ref = await storage.upload_page_image(
                    book_id=book_id,
                    chapter_no=chapter_no,
                    page_no=page_number,
                    png_bytes=png_bytes,
                )

                # 3) Accumulate the page dict for the batched append.
                #    v7: no ``object_url`` key — persistent URLs are no
                #    longer stored.  Callers that need an access URL
                #    request one via ``storage.get_public_url``.
                batch.append({
                    "page_no": page_number,
                    "plain_text": page_data.get("plain_text", ""),
                    "word_count": int(page_data.get("word_count", 0)),
                    "token_count": int(page_data.get("token_count", 0)),
                    "extraction_method": ExtractionMethod.PYMUPDF.value,
                    "object_key": ref.object_key,
                    "bucket_name": ref.bucket_name,
                    "size_bytes": len(png_bytes),
                    "mime_type": "image/png",
                })

                result.pages_processed += 1
                # Append a placeholder result; the extracted_text_id
                # is back-filled after the batch write returns the
                # object_ids.
                batch_result_indices.append(len(result.page_results))
                result.page_results.append(
                    PageProcessingResult(
                        page_number=page_number,
                        success=True,
                        processing_time_ms=round(
                            (time.time() - page_start) * 1000, 2
                        ),
                    )
                )

            except Exception as e:
                logger.exception("Page %s failed", page_number)
                err = IngestionErrorRecord(
                    stage="page_processing",
                    page_number=page_number,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                result.add_error(err)
                result.pages_failed += 1
                result.page_results.append(
                    PageProcessingResult(
                        page_number=page_number, success=False, error=err
                    )
                )
                await progress.on_error("page_processing", e, page_number)
                import asyncio
                await asyncio.sleep(0.5)

        # 4) Batch-persist all successful page objects in a single
        #    ``$push + $each`` write.  Failed pages are skipped (they
        #    were never added to ``batch``).  The returned object_ids
        #    are back-filled onto the corresponding PageProcessingResult
        #    entries so callers can correlate results with stored objects.
        if batch:
            object_ids = await books.append_processed_pages(
                book_id=book_id,
                chapter_id=chapter_id,
                pages=batch,
            )
            for idx, oid in zip(batch_result_indices, object_ids):
                result.page_results[idx].extracted_text_id = oid

        # 5) Stamp processed_pages + page_end in a single write.
        if pages:
            page_numbers = [p["page_number"] for p in pages]
            await books.finalize_chapter_ingestion(
                book_id=book_id,
                chapter_id=chapter_id,
                processed_pages=len(pages),
                page_end=max(page_numbers),
            )
    finally:
        if doc is not None:
            doc.close()


def _render_page_as_png(doc, page_index: int, dpi: int = _RENDER_DPI) -> bytes:
    """Render a single page from a fitz document as a PNG image.

    Args:
        doc: An open fitz.Document.
        page_index: 0-indexed page number.
        dpi: Resolution for rendering (default 150 DPI).

    Returns:
        PNG image as bytes.
    """
    import fitz
    page = doc[page_index]
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes("png")
