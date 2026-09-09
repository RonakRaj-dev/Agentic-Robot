"""Factory helpers for assembling the pipeline and service layer.

The factory is the ONLY place where concrete service implementations
are wired together.  Application components (pipeline, CLI, future API
endpoints) receive their dependencies through the service interfaces
defined in :mod:`interfaces` — they never construct concrete services
or repositories themselves.

Two top-level builders are exposed:

  * ``build_real_pipeline`` — wires the IngestionPipeline against real
    MongoDB + MinIO + PyMuPDF services.  Used by the production CLI
    (``ingest.py``, ``ingest_catalog.py``) and the integration tests.

  * ``build_in_memory_pipeline`` — wires the IngestionPipeline against
    in-memory mock services.  Used by unit tests and the demo script.

A ``build_service_registry`` helper is also exposed for callers that
need the full set of services (e.g. a future Webrole/API layer that
needs BookService + ExamService + PipelineRunService together).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.config import get_settings
from interfaces.book_service import IBookService
from interfaces.config_service import IConfigService
from interfaces.exam_service import IExamService
from interfaces.ingestion_error_service import IIngestionErrorService
from interfaces.ingestion_job_service import IIngestionJobService
from interfaces.object_service import IObjectService
from interfaces.pipeline_error_service import IPipelineErrorService
from interfaces.pipeline_run_service import IPipelineRunService
from interfaces.pymupdf_service import IPyMuPDFService
from interfaces.progress_callback import IProgressCallback
from interfaces.storage_service import IStorageService
from pipeline.ingestion_pipeline import IngestionPipeline
from services.mongo.book_service import MongoBookService
from services.mongo.config_service import FileConfigService
from services.mongo.exam_service import MongoExamService
from services.mongo.ingestion_error_service import MongoIngestionErrorService
from services.mongo.ingestion_job_service import MongoIngestionJobService
from services.mongo.object_service import MongoObjectService
from services.mongo.pipeline_error_service import MongoPipelineErrorService
from services.mongo.pipeline_run_service import MongoPipelineRunService
from services.pymupdf.pymupdf_service import PyMuPDFService
from services.storage.storage_adapter import MinioStorageServiceAdapter
from utils.progress_utils import LoggingProgressCallback


@dataclass
class ServiceRegistry:
    """Container holding all service instances for dependency injection.

    Application components should accept this registry (or individual
    service interfaces) as constructor arguments — they should never
    construct concrete services themselves.
    """
    book_service: IBookService
    object_service: IObjectService
    exam_service: IExamService
    pipeline_run_service: IPipelineRunService
    pipeline_error_service: IPipelineErrorService
    ingestion_job_service: IIngestionJobService
    ingestion_error_service: IIngestionErrorService
    config_service: IConfigService
    storage_service: IStorageService
    pymupdf_service: IPyMuPDFService


def build_real_registry(
    progress_callback: Optional[IProgressCallback] = None,
) -> ServiceRegistry:
    """Wire all services against real MongoDB + MinIO + PyMuPDF."""
    storage = MinioStorageServiceAdapter()
    try:
        storage.ensure_bucket()
    except Exception:
        pass

    book_service = MongoBookService()
    return ServiceRegistry(
        book_service=book_service,
        object_service=MongoObjectService(book_service=book_service),
        exam_service=MongoExamService(),
        pipeline_run_service=MongoPipelineRunService(),
        pipeline_error_service=MongoPipelineErrorService(),
        ingestion_job_service=MongoIngestionJobService(),
        ingestion_error_service=MongoIngestionErrorService(),
        config_service=FileConfigService(),
        storage_service=storage,
        pymupdf_service=PyMuPDFService(),
    )


def build_real_pipeline(
    progress_callback: Optional[IProgressCallback] = None,
) -> IngestionPipeline:
    """Wire the IngestionPipeline against real MongoDB + MinIO + PyMuPDF."""
    registry = build_real_registry(progress_callback=progress_callback)
    return IngestionPipeline(
        storage_service=registry.storage_service,
        book_service=registry.book_service,
        pymupdf_service=registry.pymupdf_service,
        progress_callback=progress_callback or LoggingProgressCallback(),
    )


def build_in_memory_registry(
    progress_callback: Optional[IProgressCallback] = None,
) -> ServiceRegistry:
    """Wire all services against in-memory mocks (for unit tests / demo)."""
    from services.mocks.mock_services import (
        InMemoryBookService,
        InMemoryConfigService,
        InMemoryExamService,
        InMemoryIngestionErrorService,
        InMemoryIngestionJobService,
        InMemoryObjectService,
        InMemoryPipelineErrorService,
        InMemoryPipelineRunService,
        InMemoryPyMuPDFService,
        InMemoryStorageService,
    )

    storage = InMemoryStorageService()
    book_service = InMemoryBookService()
    return ServiceRegistry(
        book_service=book_service,
        object_service=InMemoryObjectService(book_service=book_service),
        exam_service=InMemoryExamService(),
        pipeline_run_service=InMemoryPipelineRunService(),
        pipeline_error_service=InMemoryPipelineErrorService(),
        ingestion_job_service=InMemoryIngestionJobService(),
        ingestion_error_service=InMemoryIngestionErrorService(),
        config_service=InMemoryConfigService(),
        storage_service=storage,
        pymupdf_service=InMemoryPyMuPDFService(),
    )


def build_in_memory_pipeline(
    progress_callback: Optional[IProgressCallback] = None,
) -> tuple[IngestionPipeline, ServiceRegistry]:
    """Wire the IngestionPipeline against in-memory mocks.

    Returns ``(pipeline, registry)`` so the caller can introspect the
    mock services (e.g. assert what was stored).
    """
    registry = build_in_memory_registry(progress_callback=progress_callback)
    pipeline = IngestionPipeline(
        storage_service=registry.storage_service,
        book_service=registry.book_service,
        pymupdf_service=registry.pymupdf_service,
        progress_callback=progress_callback or LoggingProgressCallback(),
    )
    return pipeline, registry
