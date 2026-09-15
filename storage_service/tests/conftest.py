"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

NCERT_DB_ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(NCERT_DB_ROOT))


@pytest.fixture(scope="session")
def sample_pdf_path() -> Path:
    """Return the path to a small 3-page test PDF."""
    fixture = NCERT_DB_ROOT / "tests" / "fixtures" / "sample_book.pdf"
    if not fixture.exists():
        from scripts.make_test_pdf import build_pdf

        build_pdf(fixture)
    return fixture


@pytest.fixture
def in_memory_services():
    """Build the full in-memory service registry (for unit tests only)."""
    from factory import build_in_memory_registry
    return build_in_memory_registry()


@pytest.fixture
def in_memory_pipeline(in_memory_services):
    """Build a pipeline backed entirely by mock services (for unit tests only)."""
    from pipeline.ingestion_pipeline import IngestionPipeline
    from utils.progress_utils import LoggingProgressCallback

    pipeline = IngestionPipeline(
        storage_service=in_memory_services.storage_service,
        book_service=in_memory_services.book_service,
        pymupdf_service=in_memory_services.pymupdf_service,
        progress_callback=LoggingProgressCallback(),
    )
    yield pipeline, {
        "storage": in_memory_services.storage_service,
        "books": in_memory_services.book_service,
        "pymupdf": in_memory_services.pymupdf_service,
        "registry": in_memory_services,
    }


@pytest.fixture
def sample_ingestion_input(sample_pdf_path):
    """Build a minimal IngestionInput pointing at the sample PDF."""
    from models.ingestion_input import IngestionInput, BookMetadata

    return IngestionInput(
        pdf_path=sample_pdf_path,
        book_metadata=BookMetadata(
            title="NCERT Class 8 Science Sample",
            author="Test Author",
            publisher="NCERT",
        ),
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
    )
