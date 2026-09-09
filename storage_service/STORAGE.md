# Storage Layer v7 — Public Object URLs

> **TL;DR** — As of v7 the codebase no longer generates presigned URLs.
> The MinIO buckets (`pdfs`, `page-images`, default exports bucket) are
> configured as **publicly downloadable**.  Anyone who needs to fetch an
> object requests a direct public URL from
> `IStorageService.get_public_url(bucket_name, object_key)`.  URLs are
> generated on demand and never persisted to MongoDB.

---

## Why this change

In v6 the codebase moved from stored permanent URLs to on-demand
presigned URLs.  Presigned URLs added complexity (expiry management,
signature rotation, bearer-token security implications) without real
benefit when the underlying MinIO buckets were already intended to be
public.

v7 simplifies the model: **buckets are public, URLs are direct**.

```json
{
  "bucket": "pdfs",
  "object_key": "class8/history/chapter1.pdf"
}
```

The storage service remains the **single source of truth** for building
access URLs.

---

## What changed (v6 → v7)

### 1. Storage service

`IStorageService` no longer exposes:

* `generate_presigned_get_url`
* `generate_presigned_put_url`
* `get_object_url` (deprecated in v6 — removed)

`IStorageService` now exposes:

```python
get_public_url(
    bucket_name: str,
    object_name: str,
) -> str
```

Synchronous (pure local string construction — no network I/O).

### 2. Storage service implementation

`MinioStorageService`:

* Removed `generate_presigned_get_url` / `generate_presigned_put_url`.
* Removed the private `_build_url` helper.
* Added `get_public_url(bucket_name, object_name) -> str`:

  ```python
  def get_public_url(self, bucket_name: str, object_name: str) -> str:
      base = get_settings().public_storage_url.rstrip("/")
      return f"{base}/{bucket_name}/{object_name}"
  ```

* `upload_bytes` / `fput_to_bucket` now return `self.get_public_url(...)`
  instead of `_build_url(...)`.

`MinioStorageServiceAdapter`:

* Removed `generate_presigned_get_url` / `generate_presigned_put_url` /
  `get_object_url`.
* Added `get_public_url` that delegates synchronously to the
  underlying `MinioStorageService`.

`InMemoryStorageService`:

* Removed the presigned URL generators and the
  `_presigned_get_urls` / `_presigned_put_urls` tracking dicts and the
  `presigned_get_url_count()` / `presigned_put_url_count()` helpers.
* Removed `get_object_url`.
* Added `get_public_url(bucket, name) -> f"memory://{bucket}/{name}"`
  for deterministic test URLs.

### 3. Models

The deprecated URL fields remain on the Pydantic models for backward
compatibility with old Mongo records:

| Model | Field | v6 | v7 |
|---|---|---|---|
| `EmbeddedObject` | `object_url` | Optional[str] = None (deprecated) | Optional[str] = None (deprecated — unchanged) |
| `EmbeddedChapter` | `pdf_object_url` | Optional[str] = None (deprecated) | Optional[str] = None (deprecated — unchanged) |
| `ExamOutputs` | `questions_only` | Optional[str] = None (deprecated legacy URL) | Optional[str] = None (deprecated legacy URL — unchanged) |
| `ExamOutputs` | `questions_with_answers` | Optional[str] = None (deprecated legacy URL) | Optional[str] = None (deprecated legacy URL — unchanged) |
| `StorageRef` | `url` | Optional[str] = None | **REMOVED** — the dataclass now carries only `bucket_name` + `object_key` |

The structured `(bucket, object_key)` fields remain the canonical
storage reference.  Old records carrying a `*_url` field still
deserialise cleanly because the URL fields are `Optional[str]`.

### 4. Pipeline

`pipeline/chapter_ingestion.py`, `pipeline/page_processing.py`, and
`pipeline/ingestion_pipeline.py` are unchanged in behaviour — they
already wrote only `(bucket_name, object_key)` and never persisted a
URL (since v6).  Comments referencing presigned URLs have been
updated to reference `get_public_url`.

### 5. Backward compatibility

Old records that still carry `*_url` fields continue to deserialize
cleanly — the URL fields are `Optional[str]` and default to `None`.

The runtime compatibility helper — `utils/storage_compat.py` —
extracts `(bucket, object_key)` from any stored record, old or new:

```python
from utils.storage_compat import resolve_object_ref

bucket, key = resolve_object_ref(stored_page_object)
if bucket and key:
    url = storage.get_public_url(bucket, key)
```

The helper tries the structured fields first and falls back to parsing
the legacy URL via `parse_storage_url()`.  This lets consumers read
old and new records uniformly without needing a one-shot migration to
have run.

### 6. Migration script

`scripts/migrate_v6_storage_refs.py` is still valid — it back-fills
structured `(bucket, object_key)` fields from legacy URLs (idempotent,
per-field skip, `--dry-run` supported).

A new `--unset-legacy-url-fields` flag has been added that, after
back-filling, issues `$unset` operations on the legacy URL fields
(`object_url`, `pdf_object_url`, `questions_only`,
`questions_with_answers`) so the documents no longer carry stale URLs.
Recommended once v7 has been deployed and all consumers use
`get_public_url`.

```bash
# Preview back-fill
python scripts/migrate_v6_storage_refs.py --dry-run

# Apply back-fill only
python scripts/migrate_v6_storage_refs.py

# Apply back-fill + unset legacy URL fields (recommended v7 cleanup)
python scripts/migrate_v6_storage_refs.py --unset-legacy-url-fields

# Preview back-fill + unset (no writes)
python scripts/migrate_v6_storage_refs.py --dry-run --unset-legacy-url-fields
```

### 7. Configuration

One new setting (in `core/config.py`):

```env
PUBLIC_STORAGE_URL=http://localhost:9000
```

Examples:

```env
PUBLIC_STORAGE_URL=http://localhost:9000
PUBLIC_STORAGE_URL=https://storage.example.com
PUBLIC_STORAGE_URL=https://minio.my-org.com
```

This must be the URL the **end user** can reach — e.g. the
public-facing MinIO endpoint, a CDN, or a reverse proxy in front of
MinIO.  All generated URLs are constructed as
`{PUBLIC_STORAGE_URL}/{bucket}/{object_key}`.

Removed settings:

* `PRESIGNED_GET_URL_EXPIRY` (was 86400s / 24h)
* `PRESIGNED_PUT_URL_EXPIRY` (was 3600s / 1h)

Removed from `Settings`:

* `minio_url` property — was only used by the deprecated
  `get_object_url` / `_build_url` methods, both of which have been
  removed.

---

## How public URLs work

A public URL is just the bucket's public endpoint joined with the
bucket name and object key:

```
{PUBLIC_STORAGE_URL}/{bucket_name}/{object_key}
```

No signing, no expiry, no credentials in the URL.  The MinIO bucket
must have a download policy that allows anonymous GETs (this is the
v7 default for the `pdfs` and `page-images` buckets).

The URL is built **locally** — no network I/O.  Public URL generation
is cheap and can be done per-request without caching.

## Security implications

* **Buckets are public.**  Anyone with the URL can read the object.
  Do not store private/sensitive content in the public buckets.
* **URLs are not bearer tokens.**  Unlike presigned URLs, public URLs
  do not expire and cannot be revoked per-URL.  Access control is at
  the bucket level (configure MinIO bucket policies accordingly).
* **Object keys are guessable.**  Object keys follow the convention
  `books/{book_id}/chapters/{chapter_no}/page_{page_no:04d}.png`.  If
  enumeration is a concern, place a CDN or auth proxy in front of
  MinIO.
* **Use HTTPS.**  Set `PUBLIC_STORAGE_URL=https://...` so URLs travel
  encrypted over the wire.

## URL lifetime

| Aspect | Value |
|---|---|
| Lifetime | Permanent (until `PUBLIC_STORAGE_URL` changes or the object is deleted) |
| Caching | Caller may cache indefinitely — the URL does not expire |
| Rotation | Change `PUBLIC_STORAGE_URL` in `.env`; all newly-generated URLs use the new value.  Existing records do not need migration because URLs are generated on demand. |

---

## Migration strategy

### Phase 1 — Code migration (this PR, v7)

* All presigned URL generators (`generate_presigned_get_url`,
  `generate_presigned_put_url`) are removed.
* `get_public_url` is added to `IStorageService` and implemented by
  all three storage services (MinIO, adapter, mock).
* `Settings.public_storage_url` is added.
* `Settings.presigned_get_url_expiry`, `Settings.presigned_put_url_expiry`,
  `Settings.minio_url` are removed.
* `StorageRef.url` field is removed.
* `IStorageService.get_object_url` is removed (was deprecated in v6).
* `MinioStorageService._build_url` is removed.

### Phase 2 — Deploy + configure

1. Set `PUBLIC_STORAGE_URL` in `.env` to the public MinIO endpoint.
2. Configure the `pdfs` and `page-images` MinIO buckets with a public
   download policy (anonymous GET).  Example using `mc`:

   ```bash
   mc anonymous set download local/pdfs
   mc anonymous set download local/page-images
   mc anonymous set download local/ncert-rag
   ```

3. Redeploy.

### Phase 3 — Data migration (one-shot, optional)

Run the migration script to back-fill structured fields on existing
records (if any v5 records are still missing them):

```bash
python scripts/migrate_v6_storage_refs.py --dry-run
python scripts/migrate_v6_storage_refs.py
```

### Phase 4 — Cleanup (optional)

Once you've confirmed no consumer reads the legacy `*_url` fields,
remove them from existing Mongo records:

```bash
python scripts/migrate_v6_storage_refs.py --dry-run --unset-legacy-url-fields
python scripts/migrate_v6_storage_refs.py --unset-legacy-url-fields
```

This issues `$unset` on `object_url`, `pdf_object_url`,
`questions_only`, and `questions_with_answers` for every document that
has them populated.  Idempotent.

---

## End-to-end usage pattern

```python
from factory import build_real_registry
from utils.storage_compat import resolve_object_ref

registry = build_real_registry()
storage = registry.storage_service
books = registry.book_service

# Load a book and find the first chapter's first page.
book = await books.get_book(book_id)
chapter = book.chapters[0]
page_obj = chapter.objects[0]

# Resolve (bucket, object_key) — works for both old and new records.
bucket, key = resolve_object_ref(page_obj)
# → ("page-images", "books/<book_id>/chapters/1/page_0001.png")

# Generate a public URL on demand.
url = storage.get_public_url(bucket, key)
# → "https://storage.example.com/page-images/books/.../page_0001.png"

# Hand the URL to the end user.  It does not expire.
return {"url": url}
```

## Testing

Unit tests (`tests/unit/`) verify the v7 contract:

* `test_storage_business_ops.py` — `StorageRef` carries only
  `bucket_name` + `object_key`; `get_public_url` returns deterministic
  `memory://` URLs.
* `test_storage_adapter.py` — `MinioStorageServiceAdapter.get_public_url`
  delegates to `MinioStorageService.get_public_url`; URL is built from
  `Settings.public_storage_url`; trailing slash is stripped.
* `test_storage_compat.py` — `resolve_object_ref` /
  `resolve_chapter_pdf_ref` / `resolve_source_pdf_ref` /
  `resolve_exam_output_ref` work for both structured and legacy URL
  inputs.
* `test_pipeline_with_mocks.py` — pipeline no longer writes
  `object_url` / `pdf_object_url` on new records.
* `test_batching.py` — pipeline gets bucket names from `StorageRef`,
  not from settings.
* `test_exam_service.py` — `store_exam_outputs` accepts structured
  `(bucket, object_key)` pairs.

Run all unit tests:

```bash
pytest tests/unit/ -v
```

Integration tests (`tests/integration/test_pipeline_real_infra.py`)
are skipped unless real MongoDB + MinIO are reachable; they verify the
full pipeline against real infrastructure.
