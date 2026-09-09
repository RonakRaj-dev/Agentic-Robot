# Migration Guide — v6 → v7

This document explains how to migrate an existing `ncert_db_v6`
deployment to v7.  v7 removes presigned URL generation entirely and
replaces it with direct public object URLs.  The MinIO buckets
(`pdfs`, `page-images`, default exports bucket) are now configured as
publicly downloadable.

See [`STORAGE.md`](./STORAGE.md) for the architectural rationale and
[`DEPENDENCY_ANALYSIS.md`](./DEPENDENCY_ANALYSIS.md) for the full
dependency trace.

---

## At a glance

| Aspect | v6 | v7 |
|---|---|---|
| URL generation | `generate_presigned_get_url` / `_put_url` (short-lived, signed) | `get_public_url(bucket, object_key)` (direct, unsigned) |
| URL lifetime | Configurable expiry (default 24h GET, 1h PUT) | Permanent (until `PUBLIC_STORAGE_URL` changes or object deleted) |
| URL stored in Mongo | **No** — only `bucket_name` + `object_key` | **No** — unchanged |
| Bucket/key stored in Mongo | Yes | Yes (unchanged) |
| `StorageRef.url` | `Optional[str] = None` for new uploads | **REMOVED** — dataclass carries only `bucket_name` + `object_key` |
| `IStorageService.get_object_url` | Deprecated (returned permanent URL via `Settings.minio_url`) | **REMOVED** |
| `IStorageService.generate_presigned_get_url` / `_put_url` | Existed | **REMOVED** |
| `Settings.presigned_get_url_expiry` / `presigned_put_url_expiry` | 86400 / 3600 | **REMOVED** |
| `Settings.minio_url` (property) | Existed (deprecated) | **REMOVED** |
| `Settings.public_storage_url` | n/a | **ADDED** (default `http://localhost:9000`) |
| `MinioStorageService._build_url` | Existed (deprecated) | **REMOVED** |
| Pipeline writes URL | No | No (unchanged) |
| `ExamOutputs` shape | Two pairs of `(bucket, object_key)` + legacy URL fields | Unchanged |
| Buckets access policy | Private (presigned URLs required) | **Public** (download policy) |
| Backward compat | n/a | Yes — legacy URL fields kept as `Optional[str]`; compat helpers fall back to URL parsing |

---

## Step-by-step

### Step 1 — Configure MinIO buckets as publicly downloadable

Before deploying v7, configure the MinIO buckets so anonymous GETs
succeed:

```bash
mc anonymous set download local/pdfs
mc anonymous set download local/page-images
mc anonymous set download local/ncert-rag
```

(or equivalent policy via the MinIO console).

### Step 2 — Set `PUBLIC_STORAGE_URL`

Add to `.env`:

```env
PUBLIC_STORAGE_URL=https://storage.example.com
```

Use the endpoint reachable by end users — e.g. the public MinIO host,
a CDN, or a reverse proxy in front of MinIO.  All object URLs are
generated as `{PUBLIC_STORAGE_URL}/{bucket}/{object_key}`.

For local development:

```env
PUBLIC_STORAGE_URL=http://localhost:9000
```

### Step 3 — Deploy v7 code

Replace the `ncert_db_v6/` directory with the new `ncert_db_v7/`
directory (or merge the changes into your branch).

**Breaking changes** (callers must update):

1. `IStorageService.generate_presigned_get_url` / `generate_presigned_put_url`
   are removed.  Any caller doing:

   ```python
   url = storage.generate_presigned_get_url(bucket, key, expires_seconds=3600)
   ```

   must change to:

   ```python
   url = storage.get_public_url(bucket, key)
   ```

2. `IStorageService.get_object_url` is removed.  Use `get_public_url`
   instead.

3. `StorageRef.url` is removed.  Code that read `ref.url` must read
   `ref.bucket_name` + `ref.object_key` and call `get_public_url`.

4. `Settings.presigned_get_url_expiry` / `presigned_put_url_expiry`
   are removed.  Remove any references from your `.env`.

5. `Settings.minio_url` is removed.  Use `Settings.public_storage_url`
   instead.

**Non-breaking changes** (callers do not need to update):

* `IStorageService.upload_pdf` / `upload_page_image` / `upload_export`
  still return a `StorageRef` carrying `bucket_name` + `object_key`.
* `IBookService.update_chapter_pdf_ref` still accepts the optional
  `pdf_object_url` parameter (defaults to `None`).
* `IObjectService.append_page_image` still accepts the optional
  `object_url` parameter (defaults to `None`).
* `IBookService.attach_source_pdf` still accepts either `storage_url`
  OR `(bucket_name, object_key)`.
* `IExamService.store_exam_outputs` signature is unchanged.
* The legacy `*_url` fields on `EmbeddedObject`, `EmbeddedChapter`,
  `ExamOutputs` remain `Optional[str]` so old records still
  deserialize.

### Step 4 — Update any callers of removed methods

If you have a `Pipeline` / `Formator` / API component that called the
removed methods, update it:

```python
# v6
url = storage.generate_presigned_get_url(bucket, key, expires_seconds=3600)

# v7
url = storage.get_public_url(bucket, key)
```

The `utils/storage_compat.resolve_*` helpers continue to work — they
return `(bucket, key)` and the caller then calls `get_public_url`.

### Step 5 — Run the data migration (optional, recommended)

If you have v5-era records that still carry `object_url` /
`pdf_object_url` / `questions_only` / `questions_with_answers` as
non-null URL strings and have NOT yet been back-filled with structured
fields, run the migration script:

```bash
# Preview what would change
python scripts/migrate_v6_storage_refs.py --dry-run

# Apply back-fill
python scripts/migrate_v6_storage_refs.py
```

The script:

* Walks every BOOKS document and back-fills `bucket_name` +
  `object_key` on every `chapters[].objects[]` entry, every
  `chapters[]` PDF ref, and the optional `source_pdf`.
* Walks every EXAMS document and back-fills the four structured
  fields on `outputs`.
* Does NOT delete the legacy URL fields by default — they are kept
  for backward compatibility during the transition.
* Is idempotent — safe to run multiple times.

### Step 6 — (Optional) Unset legacy URL fields

Once you've confirmed all consumers use `get_public_url` and no code
path reads the legacy `*_url` fields, you can remove them from
existing Mongo records:

```bash
# Preview
python scripts/migrate_v6_storage_refs.py --dry-run --unset-legacy-url-fields

# Apply
python scripts/migrate_v6_storage_refs.py --unset-legacy-url-fields
```

This issues `$unset` on `object_url`, `pdf_object_url`,
`questions_only`, and `questions_with_answers` for every document
that has them populated.  Idempotent.

### Step 7 — Verify

Run the unit tests:

```bash
pytest tests/unit/ -v
```

All tests should pass.  If you have integration tests, run them
against real infrastructure:

```bash
pytest tests/integration/ -v
```

---

## Rollback

If v7 needs to be rolled back to v6:

1. Revert the code to v6.
2. The MinIO bucket public-download policy can stay in place — v6
   presigned URLs work whether the bucket is public or private.
3. Re-add `PRESIGNED_GET_URL_EXPIRY` / `PRESIGNED_PUT_URL_EXPIRY` to
   `.env` (v6 falls back to defaults if absent, so this is optional).
4. v6 code calls `generate_presigned_get_url` / `_put_url` — these
   methods exist in v6 and produce presigned URLs as before.
5. Any v7-era records (created between the v7 deploy and the rollback)
   have `bucket_name` + `object_key` populated — v6 code can read
   these and generate presigned URLs from them via
   `utils.storage_compat.resolve_*`.

No data migration is needed for rollback.

---

## FAQ

### Q: Do I need to take downtime during the migration?

No.  The migration script is read-modify-write per document and does
not lock the collection.  New writes (from v7 code) and old writes
(from v6 code) can coexist during the transition because both code
paths populate the structured fields.

### Q: What happens if I run v7 code without making the buckets public?

`get_public_url` will still return a URL, but end users will get a
`403 Forbidden` when they try to fetch the object.  Make sure the
bucket download policy is configured (see Step 1) before deploying v7.

### Q: Can I delete the legacy URL fields after migration?

Yes — run the migration script with `--unset-legacy-url-fields`:

```bash
python scripts/migrate_v6_storage_refs.py --unset-legacy-url-fields
```

This is recommended once you've confirmed no consumer reads them.

### Q: What about the `get_object_url` method on the storage service?

Removed in v7.  Use `get_public_url` instead.  The method was
deprecated in v6 and was the last caller of `Settings.minio_url`,
which has also been removed.

### Q: What if MinIO is behind a Cloudflare tunnel?

Set `PUBLIC_STORAGE_URL` to the tunnel URL:

```env
PUBLIC_STORAGE_URL=https://minio-tunnel.example.com
```

All generated URLs will use that endpoint.  When the tunnel URL
changes, only `.env` needs updating — no MongoDB migration is
required.  This is the primary benefit of the v7 refactor (inherited
from v6).

### Q: Can I use AWS S3 instead of MinIO?

The codebase uses the `minio` Python SDK which is S3-compatible.  To
use AWS S3, set `MINIO_ENDPOINT` to your S3 endpoint
(e.g. `s3.amazonaws.com`), provide AWS credentials as
`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`, and set `MINIO_SECURE=true`.
Set `PUBLIC_STORAGE_URL` to your S3 website endpoint or CDN.  Public
URLs will be generated against that endpoint.

Note: S3 buckets must be configured with a public-read bucket policy
(anonymous GET) for v7's public URLs to work.

### Q: How do I generate a URL for a specific object version?

The current `get_public_url` method does not expose the `version_id`
parameter.  If you need versioned URLs, extend the method to append
`?versionId=<id>` to the URL.  This is a small additive change — no
other code needs to be modified.

### Q: What about presigned PUT URLs for external-client uploads?

Removed in v7.  If you have external clients (web forms, CLI tools)
that previously used presigned PUT URLs to upload directly to MinIO,
they must now proxy uploads through your application (which uses
`IStorageService.upload_bytes` / `upload_file`).  Alternatively,
configure a separate MinIO bucket with a write policy and have
external clients upload to that bucket via direct PUT.
