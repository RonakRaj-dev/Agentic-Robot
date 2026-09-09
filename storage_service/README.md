# ncert-db — NCERT PDF Ingestion Pipeline

Production-ready PDF ingestion pipeline for NCERT textbooks, powered by **PyMuPDF** for text extraction and page rendering, **MongoDB** for structured storage, and **MinIO** for binary asset storage.

## Architecture (Schema v3, service layer v5)

```
API / CLI / pipeline
    → services (IBookService, IStorageService, IPyMuPDFService, ...)
        → repositories (BookRepository, ...)
            → MongoDB
        → StorageService (IStorageService)
            → MinIO
```

No component outside the service layer accesses repositories, Mongo
collections, or MinIO directly.  The service layer is the SINGLE API
in front of all persistence.

### Pipeline flow (catalog-driven)

```
newestbooks.json (catalog)
      ↓
Catalog Import → BOOKS collection (one document per NCERT book)
      ↓                (batched $push + $each for chapters)
For each chapter PDF:
    find existing book by pdf_filename → ingest_chapter()
    (NO create_book() — appends to existing book's chapter)
        ↓
    Upload full chapter PDF to MinIO  (StorageService.upload_pdf → StorageRef)
    Save PDF reference on EmbeddedChapter
        ↓
    PyMuPDF text extraction (page-by-page, streaming)
        ↓
    For each page:
        • Render page as PNG using PyMuPDF
        • Upload page image to MinIO  (StorageService.upload_page_image → StorageRef)
        • Accumulate PAGE_IMAGE object dicts in memory
        ↓
    Batch-persist all page objects in a SINGLE $push + $each
    Finalize chapter (processed_pages + page_end in one write)
    Adjust book.total_pages by the delta (idempotent re-ingest)
```

## Key Design Decisions (v3 + v5 + v6 + v7)

- **PyMuPDF only** — no OCR, no layout analysis
- **BOOKS is the sole aggregate root** — chapters and objects are embedded
- **NO separate CHAPTERS / OBJECTS collections**
- **Chapter PDF reference** stored directly on `EmbeddedChapter`
  (`pdf_object_key`, `pdf_bucket_name`, `pdf_size_bytes`).
  v6: `pdf_object_url` is deprecated and left as `None` for new uploads.
- **`objects[]` contains PAGE_IMAGE entries** — one PNG per page
- **`processed_pages`** counter tracks processed pages per chapter
- **`total_pages`** = sum of all pages across ALL chapter PDFs
- **One Book per NCERT book** — unique compound index prevents duplicates
- **Catalog-driven** — `newestbooks.json` is the source of truth
- **Service layer (v5)** — 11 interfaces, every component talks to
  services only; services talk to repositories; repositories talk to
  MongoDB; StorageService talks to MinIO
- **Batched writes (v5)** — page objects are persisted in a single
  `$push + $each` per chapter (was 1 `update_one` per page); chapter
  finalisation stamps `processed_pages` + `page_end` in one write
  (was two); catalog import batch-appends chapters via `add_chapters`
  (was one `add_chapter` per chapter)
- **StorageRef (v5)** — `upload_pdf` / `upload_page_image` /
  `upload_export` return a `StorageRef(bucket_name, object_key)`
  so the pipeline never reads bucket names from settings.
- **Public object URLs (v7)** — the MinIO buckets (`pdfs`,
  `page-images`, default exports bucket) are configured as publicly
  downloadable.  Access URLs are generated dynamically by
  `IStorageService.get_public_url(bucket, object_key)` from
  `Settings.public_storage_url`.  Presigned URLs have been removed
  entirely — no signing, no expiry, no URL persistence.  See
  [`STORAGE.md`](./STORAGE.md) for the full rationale and
  [`MIGRATION.md`](./MIGRATION.md) for the v6→v7 migration plan.

## Storage Layout

```
Book
└── chapters[]
    ├── pdf_object_key
    ├── pdf_bucket_name
    ├── pdf_object_url          (v6: None for new uploads — deprecated)
    ├── pdf_size_bytes
    └── objects[]
        ├── PAGE_IMAGE
        │   ├── object_key
        │   ├── bucket_name
        │   ├── object_url      (v6: None for new uploads — deprecated)
        │   └── ...
        ├── PAGE_IMAGE
        └── ...
```

See [`STORAGE.md`](./STORAGE.md) for how to generate public access URLs
from the structured `(bucket, object_key)` fields.

## Dependencies

```
pymupdf>=1.27.2.3    # PDF text extraction + page rendering
motor>=3.7.1          # Async MongoDB driver
minio>=7.2.20         # MinIO S3 client
pydantic>=2.13.4      # Data models
pydantic-settings     # Settings from .env
tenacity>=8.2.0       # Retry logic
structlog>=26.1.0     # Structured logging
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your MongoDB and MinIO credentials:
#   MONGO_URI=mongodb://localhost:27017
#   MONGO_DB_NAME=Ncert_Rag
#   MINIO_ENDPOINT=localhost:9000
#   MINIO_ACCESS_KEY=minioadmin
#   MINIO_SECRET_KEY=minioadmin
#   MINIO_SECURE=false
```

### 3. Start infrastructure

```bash
docker compose up -d minio
# (MongoDB is assumed to be running separately — point MONGO_URI at it)
```

### 4. Run catalog-driven ingestion

```bash
# Import catalog only (creates Book docs, no PDF processing)
python ingest_catalog.py --catalog newestbooks.json --import-only

# Import catalog + process all chapter PDFs
python ingest_catalog.py --catalog newestbooks.json --pdf-dir ./data/pdfs

# Limit to N chapters for testing
python ingest_catalog.py --catalog newestbooks.json --pdf-dir ./data/pdfs --limit 5
```

### 5. Run the legacy single-PDF ingestion (optional)

```bash
# Ingest a single PDF as a one-chapter book (creates the Book too)
python ingest.py ./data/pdfs/some.pdf --title "Physics" --class 11 --subject Physics
```

## Running the tests

```bash
# Unit tests (use in-memory mock services — no infrastructure needed)
pytest tests/unit/

# Integration tests (require real MongoDB + MinIO running)
pytest tests/integration/

# Run a single test file
pytest tests/unit/test_batching.py -v

# Run with live log output
pytest tests/unit/ --log-cli-level=INFO
```

## MongoDB Document Shape (v3 + v6)

```json
{
  "_id": ObjectId("..."),
  "class_no": 10,
  "subject": "English",
  "title": "Maths",
  "board": "CBSE",
  "catalog_source": "newestbooks.json",
  "total_pages": 250,
  "chapters": [
    {
      "id": ObjectId("..."),
      "chapter_no": 1,
      "title": "Real Numbers",
      "pdf_filename": "ta20181017153974729010MathsNcertchapter1.pdf",
      "chapter_code": "1",
      "preferred_llm": null,
      "catalog_source": "newestbooks.json",
      "pdf_object_key": "books/.../chapters/1/chapter.pdf",
      "pdf_bucket_name": "pdfs",
      "pdf_object_url": null,
      "pdf_size_bytes": 520000,
      "processed_pages": 22,
      "page_start": 1,
      "page_end": 22,
      "objects": [
        {
          "id": ObjectId("..."),
          "object_type": "PAGE_IMAGE",
          "object_key": "books/.../chapters/1/page_0001.png",
          "bucket_name": "page-images",
          "object_url": null,
          "page_no": 1,
          "mime_type": "image/png",
          "size_bytes": 123456,
          "metadata": {
            "plain_text": "Real Numbers\n...",
            "word_count": 320,
            "token_count": 416,
            "extraction_method": "pymupdf"
          },
          "created_at": "2026-06-28T..."
        }
      ],
      "created_at": "2026-06-28T...",
      "updated_at": "2026-06-28T..."
    }
  ],
  "metadata": {
    "language": "en",
    "board": "CBSE",
    "catalog_source": "newestbooks.json",
    "pdf_filenames": ["..."]
  },
  "created_at": "2026-06-28T...",
  "updated_at": "2026-06-28T..."
}
```

> **v7 note**: `pdf_object_url` and `objects[].object_url` are `null`
> for new uploads.  Old (v5) records may still carry a URL string in
> these fields — the runtime compatibility helper
> `utils/storage_compat.resolve_object_ref` handles both shapes.
> Generate an access URL on demand via
> `storage.get_public_url(bucket_name, object_key)` — no signing, no
> expiry.  Buckets are publicly downloadable.

## MinIO Storage Hierarchy

### Bucket: `pdfs` (chapter PDFs)

```
pdfs/
└── books/
    └── {book_id}/
        └── chapters/
            └── {chapter_no}/
                └── chapter.pdf
```

### Bucket: `page-images` (page PNGs)

```
page-images/
└── books/
    └── {book_id}/
        └── chapters/
            └── {chapter_no}/
                ├── page_0001.png
                ├── page_0002.png
                └── ...
```

## Service Layer (v5)

11 interfaces in `interfaces/`:

| Interface | Purpose |
|---|---|
| `IBookService` | BOOKS aggregate root — books, chapters, page objects, chapter PDF refs |
| `IObjectService` | Chapter-embedded object lifecycle (facade over IBookService) |
| `IExamService` | Finalized exams |
| `IPipelineRunService` | Generation-pipeline run observability |
| `IPipelineErrorService` | Generation-pipeline error log |
| `IIngestionJobService` | Ingestion job observability |
| `IIngestionErrorService` | Ingestion error log |
| `IConfigService` | Externalized AI/agent/model config (file backend) |
| `IStorageService` | Object-storage business ops (upload_pdf, upload_page_image, upload_export) — returns `StorageRef`; public URL builder: `get_public_url(bucket, object_key)` |
| `IPyMuPDFService` | Text-extraction abstraction |
| `IProgressCallback` | Pipeline progress reporting |

Every interface has a Mongo implementation (`services/mongo/`) and an
in-memory mock (`services/mocks/`).  The factory (`factory.py`)
assembles them into a `ServiceRegistry` for dependency injection.

## Testing

```bash
# Unit tests (use mock services, no infrastructure needed)
pytest tests/unit/
```
