# Storage Object Flow — Dependency Analysis

This document traces every code path that **writes**, **stores**, or **reads**
an object-storage reference (URL / bucket / object key) in the `ncert_db_v6`
codebase. It is the prerequisite for the v7 refactor that removes
presigned URL generation entirely and replaces it with direct public
object URLs (buckets are publicly downloadable).

For the v5 → v6 history (presigned URLs), see the `git log` of this
file.  The current state (v7) is documented below.

---

## 1. Components involved

| Layer | File | Role |
|---|---|---|
| Interface | `interfaces/storage_service.py` | `IStorageService` ABC + `StorageRef` dataclass |
| Interface | `interfaces/book_service.py` | `IBookService` (writes chapter PDF ref, page objects, source PDF) |
| Interface | `interfaces/object_service.py` | `IObjectService` (facade over `IBookService`) |
| Interface | `interfaces/exam_service.py` | `IExamService` (writes exam output refs) |
| Concrete | `services/storage/minio_service.py` | `MinioStorageService` — synchronous MinIO client wrapper |
| Concrete | `services/storage/storage_adapter.py` | `MinioStorageServiceAdapter` — async adapter, implements `IStorageService` |
| Concrete | `services/mongo/book_service.py` | `MongoBookService` — translates intent to Mongo writes |
| Concrete | `services/mongo/object_service.py` | `MongoObjectService` — facade over `MongoBookService` |
| Concrete | `services/mongo/exam_service.py` | `MongoExamService` — exam lifecycle |
| Concrete | `services/mocks/mock_services.py` | In-memory mocks for unit tests |
| Pipeline | `pipeline/chapter_ingestion.py` | `upload_chapter_pdf_and_attach` — uploads chapter PDF |
| Pipeline | `pipeline/page_processing.py` | `store_pages_as_images` — uploads each page PNG |
| Pipeline | `pipeline/ingestion_pipeline.py` | `IngestionPipeline` — orchestrator; legacy single-PDF path |
| Repo | `repos/mongo/book_repo.py` | `BookRepository` — atomic `$set`/`$push` writes |
| Models | `db/models/embedded.py` | `EmbeddedObject`, `EmbeddedChapter` |
| Models | `db/models/exam.py` | `ExamOutputs` |
| Models | `db/models/book.py` | `Book.source_pdf: Optional[EmbeddedObject]` |
| Config | `core/config.py` | `Settings.public_storage_url` (single source of truth for URL base) |
| Utils | `utils/oid_utils.py` | `parse_storage_url(url) -> (bucket, key)` — legacy URL fallback |
| Utils | `utils/storage_compat.py` | `resolve_object_ref` / `resolve_chapter_pdf_ref` / `resolve_source_pdf_ref` / `resolve_exam_output_ref` — uniform `(bucket, key)` extraction |

---

## 2. Where URLs are *constructed*

Only one location builds public URLs:

```
Settings.public_storage_url  →  e.g. "https://storage.example.com"
                                  ↓
MinioStorageService.get_public_url(bucket, name)        →  f"{public_storage_url}/{bucket}/{name}"
MinioStorageServiceAdapter.get_public_url(b, n)         →  delegates synchronously
InMemoryStorageService.get_public_url(b, n)             →  f"memory://{bucket}/{name}"
```

All upload paths (`upload_bytes`, `fput_to_bucket`, `upload_file`,
`upload_pdf`, `upload_page_image`, `upload_export`) return the URL
built by `get_public_url`.  Business operations (`upload_pdf`,
`upload_page_image`, `upload_export`) discard the URL internally and
return a `StorageRef(bucket_name, object_key)` carrying only the
structured reference.

---

## 3. Where URLs are *written* to Mongo

**No URLs are written to MongoDB by the v7 pipeline.**  Only
`bucket_name` + `object_key` are persisted:

### 3.1 Chapter PDF reference

```
IngestionPipeline.ingest_chapter
  └── upload_chapter_pdf_and_attach (pipeline/chapter_ingestion.py)
        ├── storage.upload_pdf(...)              →  StorageRef(bucket_name, object_key)
        └── books.update_chapter_pdf_ref(
              book_id, chapter_id,
              pdf_object_key   = ref.object_key,
              pdf_bucket_name  = ref.bucket_name,
              pdf_size_bytes   = pdf_size,
              # v7: pdf_object_url deliberately NOT passed — defaults to None
            )
              └── MongoBookService.update_chapter_pdf_ref
                    └── BookRepository.update_chapter_pdf_ref
                          └── $set:
                                chapters.$.pdf_object_key  = ...
                                chapters.$.pdf_bucket_name = ...
                                chapters.$.pdf_size_bytes  = ...
                          └── $unset:
                                chapters.$.pdf_object_url  = ""   (clears stale v5 URL)
```

### 3.2 Page image objects

```
IngestionPipeline.ingest_chapter
  └── store_pages_as_images (pipeline/page_processing.py)
        ├── for each page:
        │     ├── storage.upload_page_image(...)  →  StorageRef(bucket_name, object_key)
        │     └── batch.append({
        │           ...,
        │           object_key    = ref.object_key,
        │           bucket_name   = ref.bucket_name,
        │           # v7: no object_url key
        │           ...
        │         })
        └── books.append_processed_pages(book_id, chapter_id, pages=batch)
              └── MongoBookService.append_processed_pages
                    ├── for p in pages:
                    │     EmbeddedObject(
                    │       object_key   = p["object_key"],
                    │       bucket_name  = p["bucket_name"],
                    │       # v7: object_url is not set — defaults to None
                    │       ...
                    │     )
                    └── BookRepository.add_chapter_objects
                          └── $push: chapters.$.objects.$each = [...]
                                EmbeddedObject.to_mongo() excludes object_url when None
```

### 3.3 Source PDF (legacy single-PDF path)

```
IngestionPipeline.ingest
  ├── _upload_pdf_to_storage(input_data)
  │     └── storage.upload_file(bucket, object_name, file_path)  →  public URL (discarded)
  │     → returns StorageRef(bucket_name, object_key)
  ├── result.metadata["pdf_storage_ref"] = {"bucket": ..., "object_key": ...}  ← in-memory only
  └── books.attach_source_pdf(
        book_id, file_path, metadata,
        bucket_name=ref.bucket_name, object_key=ref.object_key,
      )
        └── MongoBookService.attach_source_pdf
              ├── EmbeddedObject(
              │     object_type  = SOURCE_PDF,
              │     object_key   = object_key,
              │     bucket_name  = bucket_name,
              │     object_url   = None,    ← v7: no URL stored
              │     ...
              │   )
              └── BookRepository.set_source_pdf
                    └── $set: source_pdf = asset.to_mongo()
                          EmbeddedObject.to_mongo() excludes object_url when None
```

### 3.4 Exam outputs

```
MongoExamService.store_exam_outputs(
  exam_id,
  questions_only_bucket,             ← structured
  questions_only_object_key,         ← structured
  questions_with_answers_bucket,     ← structured
  questions_with_answers_object_key, ← structured
  ...
)
  └── ExamOutputs(
        questions_only_bucket              = ...,
        questions_only_object_key          = ...,
        questions_with_answers_bucket      = ...,
        questions_with_answers_object_key  = ...,
        # v7: legacy URL string fields explicitly None
        questions_only         = None,
        questions_with_answers = None,
      )
  └── repo.update(exam_id, {"outputs": outputs.model_dump(), ...})
```

---

## 4. Where URLs are *read* from Mongo

**Today, no production code path reads a stored URL.**  The pipeline
only writes `(bucket, key)` references; consumers that need an access
URL build it on demand via `get_public_url`.

| Reader location | What it reads | Purpose |
|---|---|---|
| `MongoObjectService.list_chapter_objects` | returns full dicts (may include legacy `object_url` if populated) | introspection / future API |
| `MongoObjectService.get_object` | same | introspection |
| `BookRepository.find_chapter_by_no` | returns full chapter dict | pipeline internal |
| Unit tests | assert field presence | verification only |

The legacy `object_url` / `pdf_object_url` / `outputs.questions_only` /
`outputs.questions_with_answers` fields are **write-only today** — they
exist on the Pydantic models for backward compatibility with old
records, but no production code reads them.  Consumers that need an
access URL use `utils.storage_compat.resolve_*` to extract
`(bucket, key)` from any record (old or new) and then call
`storage.get_public_url(bucket, key)`.

---

## 5. Field inventory

### 5.1 `EmbeddedObject` (`db/models/embedded.py`)

| Field | Type | v7 status | Used by |
|---|---|---|---|
| `object_key` | `str` (required) | Canonical | All PAGE_IMAGE / SOURCE_PDF objects |
| `bucket_name` | `str` (required) | Canonical | All PAGE_IMAGE / SOURCE_PDF objects |
| `object_url` | `Optional[str] = None` | Deprecated (v5 backward compat — kept so old records deserialize) | Legacy reads via `utils/storage_compat` |

### 5.2 `EmbeddedChapter` (`db/models/embedded.py`)

| Field | Type | v7 status | Used by |
|---|---|---|---|
| `pdf_object_key` | `Optional[str]` | Canonical | Chapter PDF reference |
| `pdf_bucket_name` | `Optional[str]` | Canonical | Chapter PDF reference |
| `pdf_object_url` | `Optional[str] = None` | Deprecated (v5 backward compat) | Legacy reads via `utils/storage_compat` |
| `pdf_size_bytes` | `Optional[int]` | — | Chapter PDF reference |

### 5.3 `Book` (`db/models/book.py`)

| Field | Type | v7 status | Used by |
|---|---|---|---|
| `source_pdf: Optional[EmbeddedObject]` | embedded | Canonical via embedded `bucket_name`/`object_key`; legacy `object_url` deprecated | Legacy single-PDF path |

### 5.4 `ExamOutputs` (`db/models/exam.py`)

| Field | Type | v7 status | Used by |
|---|---|---|---|
| `questions_only_bucket` | `Optional[str]` | Canonical | `MongoExamService.store_exam_outputs` |
| `questions_only_object_key` | `Optional[str]` | Canonical | `MongoExamService.store_exam_outputs` |
| `questions_with_answers_bucket` | `Optional[str]` | Canonical | `MongoExamService.store_exam_outputs` |
| `questions_with_answers_object_key` | `Optional[str]` | Canonical | `MongoExamService.store_exam_outputs` |
| `questions_only` | `Optional[str] = None` | Deprecated (v5 backward compat — legacy URL string) | Legacy reads via `utils/storage_compat` |
| `questions_with_answers` | `Optional[str] = None` | Deprecated (v5 backward compat — legacy URL string) | Legacy reads via `utils/storage_compat` |

### 5.5 `StorageRef` (`interfaces/storage_service.py`)

| Field | Type | v7 status |
|---|---|---|
| `bucket_name` | `str` (required) | Canonical |
| `object_key` | `str` (required) | Canonical |
| `url` | (removed in v7) | **REMOVED** — was `Optional[str] = None` in v6 |

### 5.6 `IngestionResult` (in-memory, not persisted)

| Field | Type | v7 status |
|---|---|---|
| `metadata["pdf_storage_ref"]` | `{"bucket": ..., "object_key": ...}` | Canonical (since v6) |
| `metadata["pdf_storage_url"]` | str (`"{bucket}/{object_key}"`) | Legacy compat key — retained as a `bucket/key` slug, NOT a URL |

---

## 6. Call-path matrix (write side)

```
CLI: ingest.py / ingest_catalog.py
  ↓
factory.build_real_pipeline / build_real_registry
  ↓
IngestionPipeline.ingest_chapter / ingest
  ↓
  ├── storage.upload_pdf              → StorageRef(bucket, key)
  ├── storage.upload_page_image       → StorageRef(bucket, key)
  ├── storage.upload_file (legacy)    → public URL string (discarded by caller)
  │
  ├── books.update_chapter_pdf_ref     (writes pdf_object_key + pdf_bucket_name; $unsets pdf_object_url)
  ├── books.append_processed_pages     (writes objects[].object_key + bucket_name; object_url defaults to None)
  └── books.attach_source_pdf          (writes source_pdf.bucket_name + object_key; object_url=None)

MongoExamService.store_exam_outputs    (writes outputs.questions_only_{bucket,object_key}
                                         + outputs.questions_with_answers_{bucket,object_key};
                                         legacy URL fields left None)
```

## 7. Call-path matrix (read side, v7)

```
Future consumer (API endpoint, CLI export, etc.)
  ↓
loads Book / Exam from Mongo
  ↓
extracts (bucket_name, object_key) from:
  ├── chapter.pdf_bucket_name + chapter.pdf_object_key
  ├── chapter.objects[].bucket_name + chapter.objects[].object_key
  ├── book.source_pdf.bucket_name + book.source_pdf.object_key
  └── exam.outputs.questions_only_{bucket,object_key}
        + exam.outputs.questions_with_answers_{bucket,object_key}
  ↓
storage.get_public_url(bucket, key)
  ↓
returns direct public URL to end user
```

For old records that only carry a `*_url` field, the
`utils.storage_compat.resolve_*` helpers fall back to parsing the URL
via `parse_storage_url()` to recover `(bucket, key)`.

---

## 8. Backward-compatibility surface

Old Mongo records may contain:

```json
{
  "pdf_object_url": "http://localhost:9000/pdfs/books/.../chapter.pdf",
  "pdf_bucket_name": "pdfs",
  "pdf_object_key": "books/.../chapter.pdf",
  ...
  "objects": [
    {"object_url": "http://localhost:9000/page-images/...", "bucket_name": "page-images", "object_key": "..."}
  ]
}
```

The legacy `*_url` field is redundant given `bucket_name` + `object_key`.
The v7 compatibility strategy is:

1. **Stop writing** `object_url` / `pdf_object_url` /
   `outputs.questions_only` (string) / `outputs.questions_with_answers`
   (string) for new records (already done in v6 — unchanged in v7).
2. **Keep the fields** as `Optional[str]` on the Pydantic models so old
   records still deserialize cleanly (unchanged from v6).
3. **Provide a runtime compatibility reader** —
   `utils/storage_compat.resolve_object_ref(obj)` returns
   `(bucket, object_key)` from either the structured fields or by parsing
   the legacy URL field.  Consumers then call
   `storage.get_public_url(bucket, key)`.
4. **Provide a one-shot migration script** (`scripts/migrate_v6_storage_refs.py`)
   that walks every BOOKS and EXAMS document and back-fills the
   structured fields from the legacy URL via `parse_storage_url()`.
   With the new `--unset-legacy-url-fields` flag, the script also
   `$unset`s the legacy URL fields after back-fill — recommended v7
   cleanup.

---

## 9. What changed in v7

| Concern | v6 | v7 |
|---|---|---|
| URL generation | `generate_presigned_get_url` / `generate_presigned_put_url` (signed, short-lived) | `get_public_url` (direct, unsigned, permanent) |
| URL lifetime | Configurable expiry (default 24h GET, 1h PUT) | Permanent (until `PUBLIC_STORAGE_URL` changes or object deleted) |
| URL stored in Mongo | **No** — only `bucket_name` + `object_key` | **No** — unchanged |
| Bucket/key stored in Mongo | Yes | Yes (unchanged) |
| `StorageRef` shape | `StorageRef(bucket_name, object_key, url=None)` | `StorageRef(bucket_name, object_key)` — `url` field removed |
| `IStorageService.get_object_url` | Deprecated (returned permanent URL via `Settings.minio_url`) | **REMOVED** |
| `IStorageService.generate_presigned_get_url` / `_put_url` | Existed | **REMOVED** |
| `Settings.presigned_get_url_expiry` / `presigned_put_url_expiry` | 86400 / 3600 | **REMOVED** |
| `Settings.minio_url` (property) | Existed (deprecated) | **REMOVED** |
| `Settings.public_storage_url` | n/a | **ADDED** (default `http://localhost:9000`) |
| `MinioStorageService._build_url` | Existed (deprecated) | **REMOVED** — replaced by `get_public_url` |
| Pipeline writes URL | No | No (unchanged) |
| `ExamOutputs` shape | Two pairs of `(bucket, object_key)` + legacy URL fields | Unchanged |
| Bucket access policy | Private (presigned URLs required) | **Public** (download policy) |
| Migration script | Back-fills structured from legacy URL | Back-fills structured from legacy URL + optionally `$unset`s legacy URL fields (`--unset-legacy-url-fields` flag) |
| Settings | `minio_endpoint`, `minio_secure` + `presigned_get_url_expiry`, `presigned_put_url_expiry` | `minio_endpoint`, `minio_secure` + `public_storage_url` |
