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
    db = get_database()
    for model in MODELS:
        collection = db[model.Settings.collection]
        for index in model.Settings.indexes:
            await collection.create_index(index)
