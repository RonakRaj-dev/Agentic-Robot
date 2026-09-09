"""Service-layer interfaces for the assessment platform.

The architecture requires that every component (pipeline, agent, processor,
planner, formatter, API endpoint) talks to **services only**.  Services talk
to repositories.  Repositories talk to MongoDB.  The StorageService talks
to MinIO.  No component bypasses the service layer.

This package exposes one interface per domain aggregate:

  * ``IBookService``              — books, chapters, page objects, chapter
                                   PDF references (BOOKS is the aggregate
                                   root — chapter data is embedded)
  * ``IObjectService``            — chapter-embedded object lifecycle
                                   (PAGE_IMAGE / SOURCE_PDF / FIGURE /
                                   EXPORT).  Implemented as a thin facade
                                   over ``IBookService`` because objects
                                   live inside ``chapters[].objects[]``.
  * ``IExamService``              — finalized exams
  * ``IPipelineRunService``       — generation-pipeline run observability
  * ``IPipelineErrorService``     — generation-pipeline error log
  * ``IIngestionJobService``      — ingestion job observability
  * ``IIngestionErrorService``    — ingestion error log
  * ``IConfigService``            — externalized AI/agent/model config
  * ``IStorageService``           — object-storage (MinIO) business
                                   operations: upload_pdf,
                                   upload_page_image, upload_export,
                                   delete_object, get_public_url
  * ``IPyMuPDFService``           — text-extraction abstraction
  * ``IProgressCallback``         — pipeline progress reporting

All interface methods are **business operations** (e.g. ``create_book``,
``add_chapter``, ``record_ingestion_error``, ``complete_pipeline_run``).
Database-shaped verbs (``insert``, ``update_field``, ``find_one``) are
forbidden at this layer — they belong to the repository layer.
"""
from .book_service import IBookService
from .object_service import IObjectService
from .exam_service import IExamService
from .pipeline_run_service import IPipelineRunService
from .pipeline_error_service import IPipelineErrorService
from .ingestion_job_service import IIngestionJobService
from .ingestion_error_service import IIngestionErrorService
from .config_service import IConfigService
from .storage_service import IStorageService, StorageRef
from .pymupdf_service import IPyMuPDFService
from .progress_callback import IProgressCallback

__all__ = [
    "IBookService",
    "IObjectService",
    "IExamService",
    "IPipelineRunService",
    "IPipelineErrorService",
    "IIngestionJobService",
    "IIngestionErrorService",
    "IConfigService",
    "IStorageService",
    "StorageRef",
    "IPyMuPDFService",
    "IProgressCallback",
]
