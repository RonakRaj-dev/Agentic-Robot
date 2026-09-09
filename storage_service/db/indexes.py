"""MongoDB index creation.

Creates all indexes defined on model ``Settings.indexes`` classes,
including the unique compound index on the BOOKS collection that
prevents duplicate Book documents:

    BOOKS: unique (class_no, board, subject, title)
"""
from .models.book import Book
from .models.exam import Exam
from .models.pipeline import PipelineRun, PipelineError
from .models.ingestion import IngestionJob, IngestionError
from repos.mongo.client import get_database

# Models that own a `Settings.collection` + `Settings.indexes` pair.
MODELS = [
    Book,
    Exam,
    PipelineRun,
    PipelineError,
    IngestionJob,
    IngestionError,
]


async def create_indexes() -> None:
    """Create all indexes, including the unique compound index on BOOKS.

    The BOOKS unique index is on (class_no, board, subject, title) —
    this is the last entry in ``Book.Settings.indexes`` and is created
    with ``unique=True`` so MongoDB rejects any duplicate Book document.
    """
    db = get_database()
    for model in MODELS:
        collection = db[model.Settings.collection]
        for idx, index in enumerate(model.Settings.indexes):
            is_unique = (
                model is Book
                and len(index) == 4
                and any(k == "class_no" for k, _ in index)
                and any(k == "board" for k, _ in index)
                and any(k == "subject" for k, _ in index)
                and any(k == "title" for k, _ in index)
            )
            try:
                await collection.create_index(
                    index,
                    unique=is_unique,
                    name=(
                        f"unique_{ '_'.join(k for k, _ in index) }"
                        if is_unique
                        else None
                    ),
                )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to create index %s on %s: %s",
                    index,
                    model.Settings.collection,
                    exc,
                )
