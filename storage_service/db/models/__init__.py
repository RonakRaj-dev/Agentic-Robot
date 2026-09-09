"""Pydantic models for MongoDB documents.

Top-level collection models inherit ``MongoBase`` (which carries ``_id``).
Embedded sub-documents inherit ``_EmbeddedBase`` from ``embedded.py`` and
do NOT carry an ``_id`` field — they only carry their own ``id`` field
that uniquely identifies them inside their parent's array.

Schema v3 exports:
  * Book — aggregate root
  * EmbeddedChapter — chapter with ``objects[]`` (one PAGE_IMAGE per page)
    plus ``processed_pages`` counter and chapter PDF reference fields.
  * EmbeddedObject — page storage reference + text metadata
  * ExtractionMethod — only PYMUPDF
  * ObjectType — PAGE_IMAGE, SOURCE_PDF, FIGURE
"""

from .base import MongoBase, PyObjectId, istnow
from .book import Book
from .embedded import (
    EmbeddedChapter,
    EmbeddedObject,
    ExtractionMethod,
    ObjectType,
)
from .exam import Exam, ExamStatus, DifficultyDistribution, ExamOutputs
from .ingestion import (
    IngestionJob,
    IngestionError,
    IngestionStatus,
    IngestionStage,
)
from .pipeline import (
    PipelineRun,
    PipelineError,
    PipelineStatus,
    PipelineStage,
)

__all__ = [
    "MongoBase",
    "PyObjectId",
    "istnow",
    # Aggregate root
    "Book",
    # Embedded sub-documents
    "EmbeddedChapter",
    "EmbeddedObject",
    "ExtractionMethod",
    "ObjectType",
    # Standalone collections
    "Exam",
    "ExamStatus",
    "DifficultyDistribution",
    "ExamOutputs",
    "IngestionJob",
    "IngestionError",
    "IngestionStatus",
    "IngestionStage",
    "PipelineRun",
    "PipelineError",
    "PipelineStatus",
    "PipelineStage",
]
