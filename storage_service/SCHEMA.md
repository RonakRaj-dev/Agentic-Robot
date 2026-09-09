# NCERT RAG — Database Schema Documentation (v3 + v7)

## Overview

The NCERT RAG system uses a **single-collection document model**. All
book, chapter, and page data is embedded inside the **BOOKS** collection.
There is NO separate CHAPTERS collection and NO separate OBJECTS
collection.

Binary assets (chapter PDFs and page images) are stored in **MinIO**,
with their storage references embedded inside the BOOKS documents.

**v7**: MinIO buckets are configured as publicly downloadable.  Access
URLs are generated on demand by `IStorageService.get_public_url` from
`Settings.public_storage_url` — no presigned URLs, no URL persistence.

---

## Collections

### BOOKS (primary collection)

The BOOKS collection is the **sole aggregate root**. Each document
represents one NCERT book (e.g. "Class 10 Maths") and embeds all
chapters, which in turn embed all page data.

**Unique index:** `(class_no, board, subject, title)` — prevents
duplicate Book documents.

### Other Collections (unchanged)

| Collection | Purpose |
|---|---|
| `EXAMS` | Exam definitions (unused by ingestion pipeline) |
| `PIPELINE_RUNS` | Pipeline execution records |
| `PIPELINE_ERRORS` | Pipeline error logs |
| `INGESTION_JOBS` | Ingestion job tracking |
| `INGESTION_ERRORS` | Ingestion error logs |

---

## Document Structure

### Book Document

```
BOOKS
└── Book
    ├── _id
    ├── class_no
    ├── subject
    ├── title
    ├── board
    ├── catalog_source
    ├── total_pages           ← sum of ALL pages across ALL chapter PDFs
    ├── source_pdf            ← (optional) book-level source PDF
    ├── metadata
    ├── chapters[]
    │   ├── Chapter
    │   │   ├── id
    │   │   ├── chapter_no
    │   │   ├── title
    │   │   ├── pdf_filename         ← catalog filename
    │   │   ├── chapter_code
    │   │   ├── preferred_llm
    │   │   ├── catalog_source
    │   │   ├── pdf_object_key       ← full chapter PDF reference
    │   │   ├── pdf_bucket_name
    │   │   ├── pdf_object_url
    │   │   ├── pdf_size_bytes
    │   │   ├── processed_pages     ← counter of processed pages
    │   │   ├── page_start
    │   │   ├── page_end
    │   │   └── objects[]
    │   │       ├── PAGE_IMAGE
    │   │       ├── PAGE_IMAGE
    │   │       └── ...
    │   └── ...
    └── ...
```

### Full JSON Example

```json
{
  "_id": { "$oid": "..." },
  "class_no": 1,
  "subject": "English",
  "title": "EnglishNcert",
  "board": "CBSE",
  "catalog_source": "newestbooks.json",
  "total_pages": 13,
  "source_pdf": null,
  "chapters": [
    {
      "id": { "$oid": "..." },
      "chapter_no": 1,
      "title": "A Happy Child",
      "pdf_filename": "ta2018100615388391101EnglishNCERTChapter1.pdf",
      "chapter_code": "1",
      "preferred_llm": null,
      "catalog_source": "newestbooks.json",
      "pdf_object_key": "books/.../chapters/1/chapter.pdf",
      "pdf_bucket_name": "pdfs",
      "pdf_object_url": null,
      "pdf_size_bytes": 520000,
      "processed_pages": 13,
      "page_start": 1,
      "page_end": 13,
      "objects": [
        {
          "id": { "$oid": "..." },
          "object_type": "PAGE_IMAGE",
          "object_key": "books/.../chapters/1/page_0001.png",
          "bucket_name": "page-images",
          "object_url": null,
          "page_no": 1,
          "mime_type": "image/png",
          "size_bytes": 123456,
          "metadata": {
            "plain_text": "A Happy Child\nMy house is red...",
            "word_count": 79,
            "token_count": 102,
            "extraction_method": "pymupdf"
          },
          "created_at": { "$date": "..." }
        }
      ],
      "created_at": { "$date": "..." },
      "updated_at": { "$date": "..." }
    }
  ],
  "metadata": {
    "language": "en",
    "board": "CBSE",
    "catalog_source": "newestbooks.json",
    "chapter_count": 10,
    "pdf_filenames": ["..."]
  },
  "created_at": { "$date": "..." },
  "updated_at": { "$date": "..." }
}
```

---

## Embedded Models

### EmbeddedObject

Each page in a chapter PDF produces one `EmbeddedObject` entry inside
`chapter.objects[]`. The object carries both the MinIO storage
reference for the PNG image and the extracted text metadata.

| Field | Type | Description |
|---|---|---|
| `id` | ObjectId | Unique identifier |
| `object_type` | ObjectType | Always `PAGE_IMAGE` for page images |
| `object_key` | str | MinIO object key |
| `bucket_name` | str | MinIO bucket name |
| `object_url` | str (deprecated, v7: null for new uploads; presigned URLs removed, use `get_public_url`) | Full MinIO URL — kept for backward compat reads of old records |
| `page_no` | int | Page number (1-indexed) |
| `mime_type` | str | Always `image/png` |
| `size_bytes` | int | File size in bytes |
| `metadata` | dict | Extracted text data (see below) |
| `created_at` | datetime | Creation timestamp |

**v7 access pattern**: To get an access URL for an `EmbeddedObject`,
read `(bucket_name, object_key)` and call
`IStorageService.get_public_url(bucket_name, object_key)`.
The `utils.storage_compat.resolve_object_ref(obj)` helper returns
`(bucket, key)` for both old records (URL-only) and new records
(structured fields only).

**metadata sub-document:**

| Field | Type | Description |
|---|---|---|
| `plain_text` | str | Extracted text from the page |
| `word_count` | int | Number of words |
| `token_count` | int | Estimated token count |
| `extraction_method` | str | Always `pymupdf` |

### EmbeddedChapter

Each chapter stores its full PDF reference directly on the chapter
document (NOT inside `objects[]`). The `objects[]` array only contains
PAGE_IMAGE entries.

| Field | Type | Description |
|---|---|---|
| `id` | ObjectId | Unique identifier |
| `chapter_no` | int | Chapter number |
| `title` | str | Chapter title |
| `pdf_filename` | str | Catalog PDF filename |
| `chapter_code` | str | Catalog chapter code |
| `preferred_llm` | str (optional) | Preferred LLM model for processing this chapter |
| `catalog_source` | str | Always `newestbooks.json` |
| `pdf_object_key` | str | MinIO object key for chapter PDF |
| `pdf_bucket_name` | str | MinIO bucket for chapter PDF |
| `pdf_object_url` | str (deprecated, v6: null for new uploads) | Full MinIO URL for chapter PDF — kept for backward compat |
| `pdf_size_bytes` | int | Chapter PDF file size |
| `objects` | list[EmbeddedObject] | PAGE_IMAGE entries (one per page) |
| `processed_pages` | int | Counter of processed pages |
| `page_start` | int | First page number |
| `page_end` | int | Last page number |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

---

## ObjectType Enum

| Value | Description |
|---|---|
| `PAGE_IMAGE` | PNG image rendered from a chapter PDF page |
| `SOURCE_PDF` | Full source PDF (book-level) |
| `FIGURE` | Extracted figure image |

**`PAGE_IMAGE`** represents a PNG image rendered from a chapter PDF
page. Each page of a chapter is stored as an image. Images are uploaded
to MinIO. Images are stored inside: `BOOKS → chapters[] → objects[]`.

---

## MinIO Storage Hierarchy

### Bucket: `pdfs`

Stores full chapter PDFs.

```
pdfs/
└── books/
    └── {book_id}/
        └── chapters/
            └── {chapter_no}/
                └── chapter.pdf
```

### Bucket: `page-images`

Stores PNG images rendered from each page.

```
page-images/
└── books/
    └── {book_id}/
        └── chapters/
            └── {chapter_no}/
                ├── page_0001.png
                ├── page_0002.png
                ├── page_0003.png
                └── ...
```

---

## Ingestion Pipeline Flow

### Catalog-Driven Flow

```
newestbooks.json
    ↓
Catalog Import
    ↓
BOOKS collection (one document per NCERT book, with embedded chapters)
    ↓
For each chapter PDF:
    find existing book by pdf_filename → ingest_chapter()
    (NO create_book() — appends to existing book's chapter)
        ↓
    Upload full chapter PDF to MinIO
    Save PDF reference on EmbeddedChapter
        ↓
    PyMuPDF text extraction (page-by-page, streaming)
        ↓
    For each page:
        • Render page as PNG using PyMuPDF
        • Upload page image to MinIO
        • Create PAGE_IMAGE object
        • Store PAGE_IMAGE inside chapter.objects[]
        • Preserve extracted text metadata:
          - plain_text
          - word_count
          - token_count
        ↓
    Update processed_pages
    Update total_pages
```

### Detailed Stage Breakdown

| Stage | Description |
|---|---|
| 1. PDF validation | Validate chapter PDF is non-corrupted |
| 2. Metadata extraction | Extract page count and PDF metadata |
| 3. Accumulate total_pages | Add chapter page count to book.total_pages |
| 4. Upload chapter PDF | Upload full chapter PDF to MinIO, save ref on chapter |
| 5. PyMuPDF extraction | Extract text from each page via `page.get_text()` |
| 6. Page rendering | Render each page as PNG via `page.get_pixmap()` |
| 7. Store PAGE_IMAGE | Upload PNG to MinIO, create EmbeddedObject, append to chapter.objects[] |
| 8. Update counters | Update processed_pages and page_end on chapter |

---

## Field Semantics

### `total_pages` (Book-level)

**Definition:** The total number of pages across ALL chapter PDFs
belonging to the book.

**How it's computed:** Each chapter ingestion call adds its page count
to the book's `total_pages` via an atomic `$inc` operation.

**Example:** If a book has 3 chapters with 10, 15, and 12 pages
respectively, `total_pages = 37`.

### `processed_pages` (Chapter-level)

**Definition:** Counter tracking how many pages have been processed
for this chapter.

**How it's updated:** Set to the number of pages successfully stored
as PAGE_IMAGE objects after chapter ingestion completes.

### `objects[]` (Chapter-level)

**Definition:** Array of `EmbeddedObject` entries, one per page in
the chapter PDF.

**Content:** Each entry is a `PAGE_IMAGE` object containing:
- MinIO storage reference for the PNG image
- Page metadata (page_no, mime_type, size_bytes)
- Extracted text metadata (plain_text, word_count, token_count,
  extraction_method)

### Chapter PDF Reference Fields

**Definition:** The full chapter PDF is uploaded once to MinIO and
its reference is stored directly on the chapter document.

**Fields:**
- `pdf_object_key` — MinIO object key
- `pdf_bucket_name` — MinIO bucket name
- `pdf_object_url` — Full MinIO URL (v6: deprecated, null for new uploads; v7: presigned URLs removed, use `get_public_url`)
- `pdf_size_bytes` — File size in bytes

**v7 access pattern:** To get an access URL for a chapter PDF, read
`(pdf_bucket_name, pdf_object_key)` and call
`IStorageService.get_public_url(pdf_bucket_name, pdf_object_key)`.
The `utils.storage_compat.resolve_chapter_pdf_ref(chapter)` helper
returns `(bucket, key)` for both old and new records.

**Note:** The PDF is NOT stored inside `objects[]`. The `objects[]`
array only contains page images.

---

## Preserved Fields

The following fields are preserved and must NOT be removed, renamed,
or altered:

- `plain_text` — extracted text from each page (stored in
  `objects[].metadata.plain_text`)
- `word_count` — word count per page (stored in
  `objects[].metadata.word_count`)
- `token_count` — token count per page (stored in
  `objects[].metadata.token_count`)
- `processed_pages` — counter on each chapter tracking processed pages

---

## Removed Fields (v2 → v3)

The following fields have been removed from the schema:

- `markdown`
- `contains_math`, `contains_table`, `contains_figure_caption`
- `tables`, `formulas`, `layout_blocks`, `headings`
- `PAGE_PDF` object type (replaced by `PAGE_IMAGE`)
- Single-page PDF storage model

---

## Indexes

### BOOKS Collection

| Index | Type | Purpose |
|---|---|---|
| `(class_no, subject, title)` | Compound | Book lookup |
| `(chapters.chapter_no)` | Single | Chapter lookup |
| `(chapters.id)` | Single | Chapter ID lookup |
| `(chapters.pdf_filename)` | Single | PDF filename lookup |
| `(class_no, board, subject, title)` | Compound (unique) | Prevents duplicate books |
