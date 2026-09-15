"""Integration tests: pipeline against real MongoDB + MinIO + PyMuPDF."""
from __future__ import annotations

import os
import socket
import logging

import pytest

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


def _can_connect(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _mongo_available():
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    rest = uri.split("://", 1)[1] if "://" in uri else uri
    if "@" in rest:
        rest = rest.split("@", 1)[1]
    host, _, port_str = rest.partition(":")
    port = int(port_str) if port_str.isdigit() else 27017
    return _can_connect(host or "localhost", port)


def _minio_available():
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    host, _, port_str = endpoint.partition(":")
    port = int(port_str) if port_str.isdigit() else 9000
    return _can_connect(host or "localhost", port)


pytestmark = pytest.mark.skipif(
    not (_mongo_available() and _minio_available()),
    reason="MongoDB or MinIO not reachable",
)


@pytest.mark.asyncio
async def test_real_pipeline_end_to_end(sample_pdf_path):
    # NOTE: this test is skipped at collection time when MongoDB or MinIO
    # is not reachable (see the module-level ``pytestmark`` above).
    from factory import build_real_pipeline
    from models.ingestion_input import IngestionInput, BookMetadata

    pipeline = build_real_pipeline()
    input_data = IngestionInput(
        pdf_path=sample_pdf_path,
        book_metadata=BookMetadata(
            title="NCERT Integration Test Book", publisher="NCERT"
        ),
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
        processing_options={"ocr_enabled": True, "lang": "en"},
    )
    result = await pipeline.ingest(input_data)
    assert result.pipeline_status in {"completed", "partial_success"}
    assert result.total_pages == 3
    assert result.pages_processed >= 1
    assert result.book_id is not None
    assert result.pdf_media_asset_id is not None