"""In-memory mock services for unit testing.

Each mock implements the corresponding interface from :mod:`interfaces`.
Mocks share a single ``_new_id()`` counter so generated ids are
globally unique within a test run.

The mocks are split across one file per service for discoverability
but re-exported from this package so callers can do
``from services.mocks import InMemoryBookService``.
"""
from __future__ import annotations

import itertools
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from interfaces.book_service import IBookService
from interfaces.config_service import IConfigService
from interfaces.exam_service import IExamService
from interfaces.ingestion_error_service import IIngestionErrorService
from interfaces.ingestion_job_service import IIngestionJobService
from interfaces.object_service import IObjectService
from interfaces.pipeline_error_service import IPipelineErrorService
from interfaces.pipeline_run_service import IPipelineRunService
from interfaces.pymupdf_service import IPyMuPDFService
from interfaces.storage_service import IStorageService, StorageRef
from db.models.embedded import EmbeddedObject, ObjectType
from utils.oid_utils import parse_storage_url

logger = logging.getLogger(__name__)


# ── shared helpers ───────────────────────────────────────────────────


def _new_id() -> str:
    """Stable, sortable mock id (no ObjectId needed in tests)."""
    counter = next(_new_id._counter)  # type: ignore[attr-defined]
    return f"mock_{counter:08d}"


_new_id._counter = itertools.count(1)  # type: ignore[attr-defined]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Storage ──────────────────────────────────────────────────────────


# Hardcoded bucket names for the in-memory mock — matches the
# production settings defaults (minio_bucket_pdf="pdfs",
# minio_bucket_images="page-images", minio_bucket="ncert-rag").
_MOCK_BUCKET_PDFS = "pdfs"
_MOCK_BUCKET_IMAGES = "page-images"
_MOCK_BUCKET_EXPORTS = "ncert-rag"


class InMemoryStorageService(IStorageService):
    """Stores uploaded blobs in an in-memory dict keyed by (bucket, name).

    .. versionchanged:: v7
        Removed ``generate_presigned_get_url`` / ``generate_presigned_put_url``
        and the ``_presigned_get_urls`` / ``_presigned_put_urls``
        tracking dicts — presigned URLs have been removed entirely.
        Tests that need an access URL must call :meth:`get_public_url`.
        Removed the deprecated ``get_object_url`` method —
        :meth:`get_public_url` is now the single URL builder.
    """

    def __init__(self) -> None:
        self._blobs: Dict[tuple, bytes] = {}
        self._files: Dict[tuple, Any] = {}
        self._buckets: set[str] = set()

    # ── Business operations ─────────────────────────────────────────

    async def upload_pdf(
        self,
        book_id: str,
        chapter_no: int,
        file_path: Any,
    ) -> StorageRef:
        object_key = f"books/{book_id}/chapters/{chapter_no}/chapter.pdf"
        # upload_file returns a public URL which we discard.
        await self.upload_file(
            bucket_name=_MOCK_BUCKET_PDFS,
            object_name=object_key,
            file_path=file_path,
            content_type="application/pdf",
        )
        return StorageRef(
            bucket_name=_MOCK_BUCKET_PDFS, object_key=object_key,
        )

    async def upload_page_image(
        self,
        book_id: str,
        chapter_no: int,
        page_no: int,
        png_bytes: bytes,
    ) -> StorageRef:
        object_key = (
            f"books/{book_id}/chapters/{chapter_no}/page_{page_no:04d}.png"
        )
        await self.upload_bytes(
            bucket_name=_MOCK_BUCKET_IMAGES,
            object_name=object_key,
            data=png_bytes,
            content_type="image/png",
        )
        return StorageRef(
            bucket_name=_MOCK_BUCKET_IMAGES, object_key=object_key,
        )

    async def upload_export(
        self,
        exam_id: str,
        filename: str,
        file_path: Any,
    ) -> StorageRef:
        object_key = f"exports/{exam_id}/{filename}"
        await self.upload_file(
            bucket_name=_MOCK_BUCKET_EXPORTS,
            object_name=object_key,
            file_path=file_path,
            content_type="application/pdf",
        )
        return StorageRef(
            bucket_name=_MOCK_BUCKET_EXPORTS, object_key=object_key,
        )

    # ── Public URL generation (v7) ──────────────────────────────────

    def get_public_url(self, bucket_name: str, object_name: str) -> str:
        """Return a deterministic ``memory://`` URL for tests.

        The URL encodes the bucket + key so tests can assert on them
        without needing a real MinIO server.  No signing, no expiry.
        """
        return f"memory://{bucket_name}/{object_name}"

    # ── Low-level operations ────────────────────────────────────────

    async def upload_file(
        self, bucket_name, object_name, file_path, content_type=None,
    ) -> str:
        from pathlib import Path
        key = (bucket_name, object_name)
        self._buckets.add(bucket_name)
        self._files[key] = Path(file_path)
        self._blobs[key] = Path(file_path).read_bytes()
        return self.get_public_url(bucket_name, object_name)

    async def upload_bytes(
        self, bucket_name, object_name, data, content_type=None,
    ) -> str:
        key = (bucket_name, object_name)
        self._buckets.add(bucket_name)
        self._blobs[key] = bytes(data)
        return self.get_public_url(bucket_name, object_name)

    async def delete_object(self, bucket_name, object_name) -> bool:
        key = (bucket_name, object_name)
        existed = key in self._blobs
        self._blobs.pop(key, None)
        self._files.pop(key, None)
        return existed

    # ── Setup-time helpers ──────────────────────────────────────────

    def ensure_bucket(self) -> None:
        # No-op for in-memory; buckets are created on first upload.
        pass

    def object_exists(self, object_name: str, bucket_name: str) -> bool:
        return (bucket_name, object_name) in self._blobs

    # ── Test introspection helpers ──────────────────────────────────

    def has_object(self, bucket_name, object_name) -> bool:
        return (bucket_name, object_name) in self._blobs

    def get_bytes(self, bucket_name, object_name) -> Optional[bytes]:
        return self._blobs.get((bucket_name, object_name))

    @property
    def total_objects(self) -> int:
        return len(self._blobs)


# ── Book ─────────────────────────────────────────────────────────────


class InMemoryBookService(IBookService):
    """In-memory Book aggregate.

    Mirrors the MongoDB layout: a single dict per book, with an
    embedded ``chapters`` list whose items each carry their own
    ``objects`` array (one entry per page).
    """

    def __init__(self) -> None:
        self._books: Dict[str, Dict[str, Any]] = {}
        self._counter = 0

    # ── book lifecycle ──────────────────────────────────────────────

    async def create_book(
        self, title, class_level, subject, language, board,
        metadata, pdf_asset_id, total_pages,
    ) -> str:
        self._counter += 1
        book_id = f"book_{self._counter:06d}"
        self._books[book_id] = {
            "id": book_id,
            "title": title,
            "class_level": class_level,
            "class_no": int(re.search(r'\d+', str(class_level)).group(0)) if re.search(r'\d+', str(class_level)) else 0,
            "subject": subject,
            "language": language,
            "board": board,
            "metadata": dict(metadata or {}),
            "pdf_asset_id": pdf_asset_id,
            "total_pages": total_pages,
            "status": "created",
            "source_pdf": None,
            "chapters": [],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        return book_id

    async def get_book(self, book_id: str) -> Optional[Dict[str, Any]]:
        return self._books.get(book_id)

    async def get_book_by_code(
        self,
        class_no: int,
        subject: str,
        title: Optional[str] = None,
        board: Optional[str] = None,
    ) -> Optional[str]:
        for book_id, book in self._books.items():
            if (
                book.get("class_no") == class_no
                and book.get("subject") == subject
                and (title is None or book.get("title") == title)
                and (board is None or book.get("board") == board)
            ):
                return book_id
        return None

    async def update_book_status(self, book_id, status, metadata=None) -> bool:
        if book_id not in self._books:
            return False
        self._books[book_id]["status"] = status
        if metadata:
            self._books[book_id].setdefault("metadata", {}).update(metadata)
        return True

    async def update_book_total_pages(
        self,
        book_id: str,
        total_pages: int,
    ) -> bool:
        """Adjust ``book.total_pages`` by ``total_pages`` (delta)."""
        book = self._books.get(book_id)
        if book is None:
            return False
        book["total_pages"] = book.get("total_pages", 0) + total_pages
        return True

    # ── source PDF ──────────────────────────────────────────────────

    async def attach_source_pdf(
        self,
        book_id: str,
        file_path: Any,
        metadata: dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        """v6: prefer structured ``bucket_name`` + ``object_key`` over URL.

        Falls back to parsing ``storage_url`` via ``parse_storage_url``
        when structured fields are missing.
        """
        # Resolve structured (bucket, key) — prefer explicit args,
        # fall back to parsing the legacy URL.
        if not (bucket_name and object_key) and storage_url:
            parsed_bucket, parsed_key = parse_storage_url(storage_url)
            bucket_name = bucket_name or parsed_bucket
            object_key = object_key or parsed_key

        if not (bucket_name and object_key):
            raise ValueError(
                "attach_source_pdf requires either bucket_name + "
                "object_key, or a parseable storage_url"
            )

        asset_id = _new_id()
        asset = {
            "id": asset_id,
            "object_type": "SOURCE_PDF",
            "object_key": object_key,
            "bucket_name": bucket_name,
            "object_url": None,  # v6: no persistent URL stored
            "page_no": None,
            "mime_type": "application/pdf",
            "size_bytes": int(metadata.get("file_size", 0) or 0),
            "metadata": dict(metadata or {}),
        }
        self._books[book_id]["source_pdf"] = asset
        return asset_id

    # ── chapters ────────────────────────────────────────────────────

    async def add_chapter(
        self, book_id, chapter_no, title,
        page_start=None, page_end=None, summary=None,
        pdf_filename=None, chapter_code=None, preferred_llm=None,
        catalog_source=None,
    ) -> str:
        book = self._books[book_id]
        for ch in book["chapters"]:
            if ch["chapter_no"] == chapter_no:
                return ch["id"]
        chapter_id = _new_id()
        chapter = {
            "id": chapter_id,
            "chapter_no": chapter_no,
            "title": title,
            "summary": summary,
            "page_start": page_start,
            "page_end": page_end,
            "pdf_filename": pdf_filename,
            "chapter_code": chapter_code,
            "preferred_llm": preferred_llm,
            "catalog_source": catalog_source,
            "pdf_object_key": None,
            "pdf_bucket_name": None,
            "pdf_object_url": None,
            "pdf_size_bytes": None,
            "objects": [],
            "processed_pages": 0,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        book["chapters"].append(chapter)
        return chapter_id

    async def add_chapters(
        self,
        book_id: str,
        chapters: Sequence[Dict[str, Any]],
    ) -> bool:
        """Batch-append multiple chapters (idempotent on chapter_no)."""
        book = self._books.get(book_id)
        if book is None:
            return False
        existing_nos = {ch["chapter_no"] for ch in book["chapters"]}
        for c in chapters:
            if c["chapter_no"] in existing_nos:
                continue
            chapter_id = _new_id()
            book["chapters"].append({
                "id": chapter_id,
                "chapter_no": c["chapter_no"],
                "title": c["title"],
                "summary": c.get("summary"),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
                "pdf_filename": c.get("pdf_filename"),
                "chapter_code": c.get("chapter_code"),
                "preferred_llm": c.get("preferred_llm"),
                "catalog_source": c.get("catalog_source"),
                "pdf_object_key": None,
                "pdf_bucket_name": None,
                "pdf_object_url": None,
                "pdf_size_bytes": None,
                "objects": [],
                "processed_pages": 0,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            })
            existing_nos.add(c["chapter_no"])
        return True

    async def get_chapter(
        self,
        book_id: str,
        chapter_no: int,
    ) -> Optional[Dict[str, Any]]:
        book = self._books.get(book_id)
        if book is None:
            return None
        for ch in book["chapters"]:
            if ch["chapter_no"] == chapter_no:
                return ch
        return None

    async def find_chapter_by_pdf_filename(
        self,
        pdf_filename: str,
    ) -> Optional[Dict[str, str]]:
        for book_id, book in self._books.items():
            for ch in book.get("chapters", []):
                if ch.get("pdf_filename") == pdf_filename:
                    return {
                        "book_id": book_id,
                        "chapter_no": str(ch.get("chapter_no", "")),
                    }
        return None

    async def update_chapter_pdf_ref(
        self,
        book_id: str,
        chapter_id: str,
        pdf_object_key: str,
        pdf_bucket_name: str,
        pdf_size_bytes: int,
        pdf_object_url: Optional[str] = None,
    ) -> bool:
        """v6: ``pdf_object_url`` is optional; defaults to ``None``."""
        book = self._books.get(book_id)
        if book is None:
            return False
        for ch in book["chapters"]:
            if ch["id"] == chapter_id:
                ch["pdf_object_key"] = pdf_object_key
                ch["pdf_bucket_name"] = pdf_bucket_name
                ch["pdf_object_url"] = pdf_object_url  # v6: usually None
                ch["pdf_size_bytes"] = pdf_size_bytes
                return True
        return False

    async def finalize_chapter_ingestion(
        self,
        book_id: str,
        chapter_id: str,
        processed_pages: int,
        page_end: Optional[int] = None,
    ) -> bool:
        book = self._books.get(book_id)
        if book is None:
            return False
        for ch in book["chapters"]:
            if ch["id"] == chapter_id:
                ch["processed_pages"] = processed_pages
                if page_end is not None:
                    ch["page_end"] = page_end
                return True
        return False

    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        book = self._books.get(book_id)
        if book is None:
            return False
        for ch in book["chapters"]:
            if ch["id"] == chapter_id:
                ch["objects"] = []
                ch["processed_pages"] = 0
                return True
        return False

    # ── chapter objects (page images) ───────────────────────────────

    async def append_page_object(
        self,
        book_id: str,
        chapter_id: str,
        page_object: EmbeddedObject,
    ) -> bool:
        """Push a single page-level object into ``chapter.objects[]``."""
        book = self._books[book_id]
        chapter = next(c for c in book["chapters"] if c["id"] == chapter_id)
        chapter["objects"].append(_serialise_page_object(page_object))
        return True

    async def append_page_objects(
        self,
        book_id: str,
        chapter_id: str,
        page_objects: Sequence[EmbeddedObject],
    ) -> bool:
        """Batch-append multiple page objects (matches $push + $each)."""
        book = self._books.get(book_id)
        if book is None:
            return False
        chapter = next(
            (c for c in book["chapters"] if c["id"] == chapter_id), None,
        )
        if chapter is None:
            return False
        for po in page_objects:
            chapter["objects"].append(_serialise_page_object(po))
        return True

    async def append_processed_pages(
        self,
        book_id: str,
        chapter_id: str,
        pages: Sequence[Dict[str, Any]],
    ) -> List[str]:
        """Batch-append multiple processed pages as PAGE_IMAGE objects.

        v6: ``object_url`` is optional in each page dict (defaults to
        ``None``).
        """
        page_objects: List[EmbeddedObject] = []
        for p in pages:
            page_objects.append(EmbeddedObject(
                object_type=ObjectType.PAGE_IMAGE,
                object_key=p["object_key"],
                bucket_name=p["bucket_name"],
                object_url=p.get("object_url"),  # v6: usually None
                page_no=p["page_no"],
                mime_type=p.get("mime_type", "image/png"),
                size_bytes=p["size_bytes"],
                metadata={
                    "plain_text": p.get("plain_text", ""),
                    "word_count": int(p.get("word_count", 0)),
                    "token_count": int(p.get("token_count", 0)),
                    "extraction_method": p.get("extraction_method", "pymupdf"),
                },
            ))
        if not page_objects:
            return []
        ok = await self.append_page_objects(
            book_id=book_id,
            chapter_id=chapter_id,
            page_objects=page_objects,
        )
        if not ok:
            raise RuntimeError("append_processed_pages failed")
        return [str(po.id) for po in page_objects]

    # ── read-only views used by tests ────────────────────────────────

    @property
    def all_books(self) -> List[Dict[str, Any]]:
        return list(self._books.values())


def _serialise_page_object(page_object: EmbeddedObject) -> Dict[str, Any]:
    """Serialise an EmbeddedObject to the dict shape stored in memory."""
    return {
        "id": str(page_object.id),
        "object_type": page_object.object_type.value,
        "object_key": page_object.object_key,
        "bucket_name": page_object.bucket_name,
        "object_url": page_object.object_url,
        "page_no": page_object.page_no,
        "mime_type": page_object.mime_type,
        "size_bytes": page_object.size_bytes,
        "metadata": page_object.metadata,
        "created_at": page_object.created_at.isoformat()
                      if hasattr(page_object.created_at, "isoformat")
                      else page_object.created_at,
    }


# ── Object (facade over Book) ────────────────────────────────────────


class InMemoryObjectService(IObjectService):
    """In-memory Object service — facade over :class:`InMemoryBookService`."""

    def __init__(self, book_service: Optional[IBookService] = None) -> None:
        self._books = book_service or InMemoryBookService()

    async def append_page_image(
        self,
        book_id: str,
        chapter_id: str,
        page_no: int,
        object_key: str,
        bucket_name: str,
        size_bytes: int,
        plain_text: str = "",
        word_count: int = 0,
        token_count: int = 0,
        extraction_method: str = "pymupdf",
        mime_type: str = "image/png",
        object_url: Optional[str] = None,
    ) -> str:
        """v6: ``object_url`` is optional; defaults to ``None``."""
        ids = await self._books.append_processed_pages(
            book_id=book_id,
            chapter_id=chapter_id,
            pages=[{
                "page_no": page_no,
                "plain_text": plain_text,
                "word_count": word_count,
                "token_count": token_count,
                "extraction_method": extraction_method,
                "object_key": object_key,
                "bucket_name": bucket_name,
                "object_url": object_url,
                "size_bytes": size_bytes,
                "mime_type": mime_type,
            }],
        )
        return ids[0] if ids else ""

    async def append_source_pdf(
        self,
        book_id: str,
        file_path: Any,
        metadata: dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        """v6: prefer structured ``bucket_name`` + ``object_key``."""
        return await self._books.attach_source_pdf(
            book_id=book_id,
            file_path=file_path,
            metadata=metadata,
            storage_url=storage_url,
            bucket_name=bucket_name,
            object_key=object_key,
        )

    async def list_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> list[dict[str, Any]]:
        book = await self._books.get_book(book_id)
        if book is None:
            return []
        chapters = book.get("chapters") if isinstance(book, dict) else getattr(book, "chapters", [])
        for ch in chapters:
            ch_id = ch.get("id") if isinstance(ch, dict) else str(getattr(ch, "id", ""))
            if str(ch_id) == str(chapter_id):
                objs = ch.get("objects") if isinstance(ch, dict) else getattr(ch, "objects", [])
                return [o if isinstance(o, dict) else o.model_dump() for o in objs]
        return []

    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        return await self._books.clear_chapter_objects(
            book_id=book_id, chapter_id=chapter_id,
        )

    async def get_object(
        self,
        book_id: str,
        chapter_id: str,
        object_id: str,
    ) -> Optional[dict[str, Any]]:
        objs = await self.list_chapter_objects(book_id, chapter_id)
        for o in objs:
            oid = o.get("id") if isinstance(o, dict) else None
            if str(oid) == str(object_id):
                return o
        return None


# ── Exam ─────────────────────────────────────────────────────────────


class InMemoryExamService(IExamService):
    """In-memory Exam service."""

    def __init__(self) -> None:
        self._exams: Dict[str, Dict[str, Any]] = {}

    async def create_exam(
        self,
        book_id: str,
        title: str,
        chapter_ids: list[str],
        duration_minutes: int,
        request_config: Optional[dict[str, Any]] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> str:
        exam_id = _new_id()
        self._exams[exam_id] = {
            "id": exam_id,
            "book_id": book_id,
            "title": title,
            "chapter_ids": list(chapter_ids),
            "duration_minutes": duration_minutes,
            "request_config": request_config,
            "pipeline_run_id": pipeline_run_id,
            "generator_version": (
                str(request_config.get("version")) if request_config else None
            ),
            "total_marks": 0,
            "question_count": 0,
            "difficulty_distribution": None,
            "qa_bundle": None,
            "outputs": {
                # v6 canonical structured fields
                "questions_only_bucket": None,
                "questions_only_object_key": None,
                "questions_with_answers_bucket": None,
                "questions_with_answers_object_key": None,
                # legacy URL string fields — None for new records
                "questions_only": None,
                "questions_with_answers": None,
            },
            "status": "draft",
            "created_at": _now_iso(),
            "generated_at": None,
        }
        return exam_id

    async def get_exam(self, exam_id: str) -> Optional[Dict[str, Any]]:
        return self._exams.get(exam_id)

    async def update_exam_status(self, exam_id: str, status: str) -> bool:
        if exam_id not in self._exams:
            return False
        self._exams[exam_id]["status"] = status
        return True

    async def store_exam_outputs(
        self,
        exam_id: str,
        total_marks: int,
        question_count: int,
        questions_only_bucket: Optional[str] = None,
        questions_only_object_key: Optional[str] = None,
        questions_with_answers_bucket: Optional[str] = None,
        questions_with_answers_object_key: Optional[str] = None,
        difficulty_distribution: Optional[dict[str, int]] = None,
        qa_bundle: Optional[dict[str, Any]] = None,
    ) -> bool:
        """v6: store structured ``(bucket, object_key)`` pairs, not URLs."""
        if exam_id not in self._exams:
            return False
        exam = self._exams[exam_id]
        exam["outputs"] = {
            # v6 canonical structured fields
            "questions_only_bucket": questions_only_bucket,
            "questions_only_object_key": questions_only_object_key,
            "questions_with_answers_bucket": questions_with_answers_bucket,
            "questions_with_answers_object_key": questions_with_answers_object_key,
            # legacy URL string fields — None for new records
            "questions_only": None,
            "questions_with_answers": None,
        }
        exam["total_marks"] = total_marks
        exam["question_count"] = question_count
        exam["status"] = "generated"
        exam["generated_at"] = _now_iso()
        if difficulty_distribution:
            exam["difficulty_distribution"] = dict(difficulty_distribution)
        if qa_bundle:
            exam["qa_bundle"] = qa_bundle
        return True

    async def list_exams_by_book(self, book_id: str) -> list[Dict[str, Any]]:
        return [e for e in self._exams.values() if e["book_id"] == book_id]


# ── PipelineRun ──────────────────────────────────────────────────────


class InMemoryPipelineRunService(IPipelineRunService):
    """In-memory PipelineRun service."""

    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}

    async def create_run(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        run_id = _new_id()
        self._runs[run_id] = {
            "id": run_id,
            "book_id": book_id,
            "pipeline_version": pipeline_version,
            "status": "running",
            "current_stage": None,
            "processed_pages": 0,
            "total_questions_generated": 0,
            "total_exams_generated": 0,
            "started_at": _now_iso(),
            "completed_at": None,
        }
        return run_id

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    async def update_progress(
        self,
        run_id: str,
        processed_pages: Optional[int] = None,
        total_questions_generated: Optional[int] = None,
        total_exams_generated: Optional[int] = None,
    ) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        if processed_pages is not None:
            run["processed_pages"] += processed_pages
        if total_questions_generated is not None:
            run["total_questions_generated"] += total_questions_generated
        if total_exams_generated is not None:
            run["total_exams_generated"] += total_exams_generated
        return True

    async def update_stage(self, run_id: str, stage: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        run["current_stage"] = stage
        return True

    async def complete_run(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        run["status"] = "completed"
        run["completed_at"] = _now_iso()
        return True

    async def fail_run(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        run["status"] = "failed"
        run["completed_at"] = _now_iso()
        return True


# ── PipelineError ────────────────────────────────────────────────────


class InMemoryPipelineErrorService(IPipelineErrorService):
    """In-memory PipelineError service."""

    def __init__(self) -> None:
        self._errors: List[Dict[str, Any]] = []

    async def record_error(
        self,
        pipeline_run_id: str,
        stage: str,
        error_code: str,
        error_message: Optional[str] = None,
        component: Optional[str] = None,
        input_reference: Optional[str] = None,
        is_fatal: bool = False,
        stack_trace: Optional[str] = None,
    ) -> str:
        error_id = _new_id()
        self._errors.append({
            "id": error_id,
            "pipeline_run_id": pipeline_run_id,
            "stage": stage,
            "error_code": error_code,
            "error_message": error_message,
            "component": component,
            "input_reference": input_reference,
            "is_fatal": is_fatal,
            "stack_trace": stack_trace,
            "created_at": _now_iso(),
        })
        return error_id

    async def list_errors(self, run_id: str) -> list[Dict[str, Any]]:
        return [e for e in self._errors if e["pipeline_run_id"] == run_id]

    async def list_fatal_errors(self, run_id: str) -> list[Dict[str, Any]]:
        return [
            e for e in self._errors
            if e["pipeline_run_id"] == run_id and e["is_fatal"]
        ]


# ── IngestionJob ─────────────────────────────────────────────────────


class InMemoryIngestionJobService(IIngestionJobService):
    """In-memory IngestionJob service."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}

    async def create_job(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        job_id = _new_id()
        self._jobs[job_id] = {
            "id": job_id,
            "book_id": book_id,
            "pipeline_version": pipeline_version,
            "status": "running",
            "pdf_parsed": 0,
            "images_extracted": 0,
            "error_count": 0,
            "started_at": _now_iso(),
            "completed_at": None,
        }
        return job_id

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)

    async def update_progress(
        self,
        job_id: str,
        pdf_parsed: Optional[int] = None,
        images_extracted: Optional[int] = None,
    ) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if pdf_parsed is not None:
            job["pdf_parsed"] += pdf_parsed
        if images_extracted is not None:
            job["images_extracted"] += images_extracted
        return True

    async def complete_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job["status"] = "completed"
        job["completed_at"] = _now_iso()
        return True

    async def fail_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job["status"] = "failed"
        job["completed_at"] = _now_iso()
        return True


# ── IngestionError ───────────────────────────────────────────────────


class InMemoryIngestionErrorService(IIngestionErrorService):
    """In-memory IngestionError service."""

    def __init__(self) -> None:
        self._errors: List[Dict[str, Any]] = []

    async def record_error(
        self,
        ingestion_job_id: str,
        stage: str,
        error_code: str,
        error_message: Optional[str] = None,
        page_no: Optional[int] = None,
        is_fatal: bool = False,
        stack_trace: Optional[str] = None,
    ) -> str:
        error_id = _new_id()
        self._errors.append({
            "id": error_id,
            "ingestion_job_id": ingestion_job_id,
            "stage": stage,
            "error_code": error_code,
            "error_message": error_message,
            "page_no": page_no,
            "is_fatal": is_fatal,
            "stack_trace": stack_trace,
            "created_at": _now_iso(),
        })
        return error_id

    async def list_errors(self, job_id: str) -> list[Dict[str, Any]]:
        return [e for e in self._errors if e["ingestion_job_id"] == job_id]

    async def list_fatal_errors(self, job_id: str) -> list[Dict[str, Any]]:
        return [
            e for e in self._errors
            if e["ingestion_job_id"] == job_id and e["is_fatal"]
        ]


# ── Config ───────────────────────────────────────────────────────────


class InMemoryConfigService(IConfigService):
    """In-memory Config service — returns a default config document.

    Implements :class:`IConfigService` with no-op ``create_indexes``
    (in-memory has no indexes) and a static default config so unit
    tests don't need a config file.
    """

    DEFAULT_CONFIG: dict[str, Any] = {
        "version": 3,
        "model_roles": {
            "default": {"provider": "openai", "model_name": "<general>"},
            "math": {"provider": "dashscope", "model_name": "<reasoning>"},
            "validator": {"provider": "anthropic", "model_name": "<general>"},
            "vision": {"provider": "openai", "model_name": "<multimodal>"},
        },
        "agents": {
            "planner": {
                "system_prompt": "",
                "model": "default",
                "tools": ["allocate", "conformance_count"],
            },
        },
        "generation": {
            "temperature": 0.4,
            "max_refine": 2,
            "max_topup": 3,
        },
        "validation": {
            "difficulty_confidence_min": 0.6,
            "dedup_text_threshold": 0.9,
        },
    }

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self._config = config or self.DEFAULT_CONFIG.copy()
        self._indexes_created = False

    async def get_config(self) -> dict[str, Any]:
        return self._config

    async def validate_config(self) -> list[str]:
        return []

    async def reload_config(self) -> dict[str, Any]:
        return self._config

    async def create_indexes(self) -> None:
        self._indexes_created = True


# ── PyMuPDF ──────────────────────────────────────────────────────────


class InMemoryPyMuPDFService(IPyMuPDFService):
    """Mock PyMuPDF service that returns per-page text output.

    When PyMuPDF is available, uses ``fitz`` to extract real text from
    the PDF; otherwise generates simple placeholder content.
    """

    def __init__(self) -> None:
        self._calls = 0

    async def extract_pages(
        self, pdf_path, book_id="",
    ) -> Dict[str, Any]:
        self._calls += 1

        total_pages = 3  # default fallback
        use_real_text = False
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            total_pages = doc.page_count
            use_real_text = True
        except Exception:
            logger.debug(
                "InMemoryPyMuPDFService: PyMuPDF unavailable, "
                "using placeholder content"
            )

        pages: List[Dict[str, Any]] = []

        if use_real_text:
            for idx in range(total_pages):
                page = doc[idx]
                text = page.get_text()
                word_count = len(text.split()) if text.strip() else 0
                pages.append({
                    "page_number": idx + 1,
                    "plain_text": text,
                    "word_count": word_count,
                    "token_count": int(word_count * 1.3),
                })
            doc.close()
        else:
            for idx in range(total_pages):
                text = f"Mock content for page {idx + 1}."
                pages.append({
                    "page_number": idx + 1,
                    "plain_text": text,
                    "word_count": 6,
                    "token_count": 8,
                })

        return {
            "pages": pages,
            "total_pages": total_pages,
        }

    @property
    def call_count(self) -> int:
        return self._calls
