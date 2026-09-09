"""Unified exception hierarchy for ncert_db."""

from typing import Optional, Any


class NCERTRagError(Exception):
    """Root exception for the entire application."""


class DomainError(NCERTRagError):
    """Violation of a domain/business rule."""


class ValidationError(DomainError):
    """Input failed domain-level validation."""


class RepositoryError(NCERTRagError):
    """Database operation failed."""


class DocumentNotFoundError(RepositoryError):
    def __init__(self, collection: str, identifier: str):
        super().__init__(f"Document not found in {collection}: {identifier}")
        self.collection = collection
        self.identifier = identifier


class DuplicateDocumentError(RepositoryError):
    def __init__(self, collection: str, key: str):
        super().__init__(f"Duplicate key in {collection}: {key}")
        self.collection = collection
        self.key = key


class ServiceError(NCERTRagError):
    """Business logic / orchestration failed."""


class IngestionError(ServiceError):
    """PDF ingestion pipeline failed (base for fine-grained subtypes)."""

    def __init__(
        self,
        message: str,
        stage: str = "unknown",
        page_no: int | None = None,
        details: Any = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.page_no = page_no
        self.details = details


class ExtractionError(ServiceError):
    """Text extraction (PyMuPDF) failed."""


# Fine-grained ingestion subtypes
class PDFValidationError(IngestionError):
    def __init__(self, message: str, details: Any = None):
        super().__init__(message, stage="pdf_validation", details=details)


class PDFCorruptedError(IngestionError):
    def __init__(self, message: str, details: Any = None):
        super().__init__(message, stage="pdf_validation", details=details)


class MinIOUploadError(IngestionError):
    def __init__(
        self,
        message: str,
        object_name: Optional[str] = None,
        page_no: Optional[int] = None,
        details: Any = None,
    ):
        super().__init__(
            message, stage="minio_upload", page_no=page_no, details=details
        )
        self.object_name = object_name


class MongoWriteError(IngestionError):
    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        page_no: Optional[int] = None,
        details: Any = None,
    ):
        super().__init__(message, stage="mongo_write", page_no=page_no, details=details)
        self.collection = collection


class MetadataExtractionError(IngestionError):
    def __init__(self, message: str, details: Any = None):
        super().__init__(message, stage="metadata_extraction", details=details)
