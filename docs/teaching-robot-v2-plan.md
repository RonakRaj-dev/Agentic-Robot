# AI Teaching Robot — Version 2 System Plan

**Purpose of this document:** This is a build specification for a coding agent. Every section states exact decisions, contracts, and constraints. Where a decision has not been finalized, it is marked `ASSUMPTION` with the reasoning — the coding agent should treat these as defaults to implement, not questions to stall on. Do not invent alternative libraries, model names, or schemas beyond what's specified here.

---

## 1. Project Goal

Build a curriculum-grounded educational Q&A system for a physical/virtual teaching robot. The system must:
- Answer student questions using **curriculum content first**, LLM generation only when necessary.
- Guarantee answers are **safe, age-appropriate, and factually grounded** in ingested curriculum documents.
- Minimize LLM token usage by resolving as many queries as possible via **semantic search + retrieval**, falling back to LLM generation only for synthesis/paraphrasing, not fact invention.
- Be modular: every capability is an independent, testable, replaceable **agent**.

Out of scope for V2: speech-to-text/text-to-speech integration, robot motor control, multi-language support (English only for V2).

---

## 2. Tech Stack (Locked — do not substitute)

| Layer | Choice | Version | Notes |
|---|---|---|---|
| Agent orchestration | AgentScope | v1.x (async API) | Use async `await` patterns throughout — v1.x changed from sync to async internally. Do not mix sync/async agent calls. |
| LLM provider | Groq | `llama-3.3-70b-versatile` | All tool/function parameters passed to this model **must be flat scalars** (str, int, float, bool) — no nested objects/arrays as direct tool parameters. Nested data must be JSON-stringified before passing. |
| Backend framework | FastAPI | latest stable | Async endpoints throughout, matching AgentScope's async model. |
| Metadata/document DB | MongoDB Atlas | latest driver (motor for async) | Use `is not None` for existence checks on MongoDB documents/fields — never truthiness (`if doc:`), since valid documents like `{}` or `0`/`False` field values evaluate falsy and cause silent bugs. |
| Vector DB | ChromaDB | latest | `ASSUMPTION`: chosen over FAISS because it has native metadata filtering (needed for curriculum-version and subject/grade filtering) and persists to disk without a separate serialization step. FAISS would require a manual sidecar metadata store; Chroma bundles this. |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` | — | `ASSUMPTION`: 384-dim, fast, good baseline for curriculum text. Swap only if retrieval quality benchmarking shows it's insufficient. |
| Cross-encoder re-ranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | — | Used for re-ranking top-K retrieved chunks before passing to Teaching Agent. |
| Frontend | React | — | Out of scope for this document; API contract only. |

**Secrets handling (mandatory):** All API keys (Groq, MongoDB URI) must be loaded via `python-dotenv` from a `.env` file that is git-ignored. Never hardcode keys in source, notebooks, or logs. Never print full key values in debug output — mask to last 4 characters if logging is needed.

---

## 3. Agent Architecture

### 3.1 Agent list and single responsibilities

| # | Agent | Responsibility | Input | Output |
|---|---|---|---|---|
| 1 | Supervisor Agent | Orchestrates the pipeline, routes query through the correct agent sequence, handles errors/fallbacks | Raw student query + session context | Final response payload |
| 2 | Validation Agent | Checks query is well-formed, non-empty, in-scope (educational) | Raw query | `{valid: bool, reason: str}` |
| 3 | Safety Agent | Filters unsafe, inappropriate, or off-curriculum content in both query and generated response | Query or draft response | `{safe: bool, flagged_reason: str|None}` |
| 4 | Retrieval Planner Agent | Decides retrieval strategy: which grade/subject filter, whether query rewriting is needed, how many chunks to fetch | Validated query + student metadata (grade, subject) | `{rewritten_query: str, filters: dict, top_k: int}` |
| 5 | Curriculum RAG Agent | Executes hybrid retrieval (vector + keyword) against ChromaDB, applies cross-encoder re-ranking | Retrieval plan | `List[RetrievedChunk]` (with scores, citations) |
| 6 | Teaching Agent | Synthesizes a pedagogically appropriate answer from retrieved chunks; calls LLM only for phrasing/explanation, not fact generation | Retrieved chunks + query | Draft answer with inline citation markers |
| 7 | Fact Verification Agent | Cross-checks every factual claim in the draft answer against the source chunks it cites; flags unsupported claims | Draft answer + source chunks | `{verified: bool, unsupported_claims: List[str]}` |
| 8 | Response Agent | Formats final response (citations, confidence score, follow-up suggestions), logs interaction | Verified answer | Final `ResponsePayload` (see §5) |

### 3.2 Orchestration flow (sequence)

```
Student Query
  → Supervisor
    → Validation Agent (reject if invalid → return polite error, END)
    → Safety Agent (on query) (reject if unsafe → return safe refusal, END)
    → Retrieval Planner Agent
    → Curriculum RAG Agent
        → IF no chunks above confidence threshold (see §6.3):
            → Supervisor decides: (a) broaden filters and retry once, or
              (b) return "insufficient curriculum coverage" response, END
    → Teaching Agent
    → Fact Verification Agent
        → IF unsupported_claims non-empty:
            → Teaching Agent re-generates using ONLY verified chunks (max 1 retry)
            → IF still unsupported after retry → strip unsupported sentences, flag low confidence
    → Safety Agent (on final draft, second pass)
    → Response Agent
  → Final Response returned to student interface
```

**Non-negotiable rule for the coding agent:** No agent other than the Teaching Agent may call the LLM for content generation. Validation, Safety (query-side), Retrieval Planner, and Fact Verification should use rule-based/regex/classifier logic or small deterministic prompts — NOT open-ended generation — to keep the pipeline auditable and cheap. Safety Agent may use a lightweight classifier call, not full generation.

---

## 4. RAG Ingestion Pipeline

### 4.1 Ingestion steps
1. **Source intake**: Curriculum PDFs/docs placed in `data/curriculum_raw/{grade}/{subject}/`.
2. **Text extraction**: Extract text page-by-page, preserving page numbers for citation.
3. **Chunking**: Recursive character splitting, **chunk size 500 tokens, overlap 50 tokens**. `ASSUMPTION`: 500/50 balances retrieval precision with enough context per chunk for a cross-encoder to score meaningfully — adjust only after retrieval quality testing, not by default.
4. **Metadata tagging per chunk**: `{grade, subject, chapter, page_number, source_file, curriculum_version, chunk_id, ingestion_date}`.
5. **Embedding generation**: Batch-embed chunks via the embedding model in §2, store vectors in ChromaDB with the metadata above attached.
6. **MongoDB mirror**: Store full chunk text + metadata in MongoDB `curriculum_chunks` collection (ChromaDB holds vectors + metadata only, not authoritative text — MongoDB is source of truth for text, to avoid drift).
7. **Versioning**: Every ingestion run is tagged with a `curriculum_version` (semver-like, e.g. `2026.1`). Old versions are never deleted — queries filter to the **active** version via a `curriculum_config` collection storing `{subject: active_version}`.

### 4.2 Curriculum versioning rules
- New curriculum uploads create a new version; they do not overwrite chunks in place.
- Only one version per `(grade, subject)` pair can be "active" at a time.
- Retrieval always filters on `curriculum_version == active_version` unless explicitly querying historical content (not needed in V2).

---

## 5. Data Contracts (exact schemas — coding agent must implement these exactly)

### 5.1 MongoDB collections

**`curriculum_chunks`**
```json
{
  "_id": "ObjectId",
  "chunk_id": "str (uuid)",
  "text": "str",
  "grade": "int",
  "subject": "str",
  "chapter": "str",
  "page_number": "int",
  "source_file": "str",
  "curriculum_version": "str",
  "ingestion_date": "datetime"
}
```

**`curriculum_config`**
```json
{
  "_id": "ObjectId",
  "subject": "str",
  "grade": "int",
  "active_version": "str"
}
```

**`interaction_logs`**
```json
{
  "_id": "ObjectId",
  "session_id": "str",
  "student_query": "str",
  "rewritten_query": "str",
  "retrieved_chunk_ids": ["str"],
  "final_answer": "str",
  "confidence_score": "float",
  "flagged": "bool",
  "timestamp": "datetime"
}
```

### 5.2 Inter-agent payloads (Python type hints, use Pydantic models)

```python
class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    page_number: int
    chapter: str
    vector_score: float
    rerank_score: float

class RetrievalPlan(BaseModel):
    rewritten_query: str
    filters: dict  # {"grade": int, "subject": str, "curriculum_version": str}
    top_k: int

class DraftAnswer(BaseModel):
    text: str
    cited_chunk_ids: list[str]

class VerificationResult(BaseModel):
    verified: bool
    unsupported_claims: list[str]

class ResponsePayload(BaseModel):
    answer: str
    citations: list[dict]  # [{"source_file": str, "page_number": int, "chapter": str}]
    confidence_score: float  # 0.0-1.0
    flagged: bool
    session_id: str
```

**Critical constraint for Groq/LLaMA tool calls:** When any agent step calls the LLM with tool/function definitions, tool parameters passed in the function schema must be flat (str/int/float/bool) per §2. If a nested structure like `RetrievalPlan.filters` needs to go into a tool call, serialize it to a JSON string parameter (e.g. `filters_json: str`) and deserialize on the receiving end — do not define nested object parameters directly in the tool schema.

---

## 6. Retrieval Details

### 6.1 Hybrid retrieval
- **Vector search**: ChromaDB similarity search (cosine) over the query embedding, filtered by `grade`, `subject`, `curriculum_version`.
- **Keyword search**: BM25 over the same filtered chunk set (maintain a parallel BM25 index in-memory per subject, rebuilt on ingestion, since ChromaDB alone doesn't do keyword matching well for named entities/numbers).
- **Fusion**: Combine vector + BM25 results via **Reciprocal Rank Fusion (RRF)**, k=60. `ASSUMPTION`: RRF chosen over weighted score averaging because vector cosine scores and BM25 scores are not on comparable scales; RRF is scale-invariant.

### 6.2 Query rewriting
- Retrieval Planner Agent rewrites colloquial/ambiguous student queries into curriculum-search-friendly form (e.g., "why does ice float" → "density of ice vs water buoyancy"). This is a small, constrained LLM call with a strict system prompt: output ONLY the rewritten query, no explanation, no additional facts. Temperature 0.

### 6.3 Confidence thresholding
- After re-ranking, if the **top chunk's rerank_score < 0.35** (`ASSUMPTION`: calibrate empirically during testing; start here), treat as "insufficient curriculum coverage."
- Confidence score for the final response = normalized average of top-3 rerank scores, mapped to 0.0–1.0.

### 6.4 Re-ranking
- Take top 20 chunks from hybrid retrieval (Reciprocal Rank Fusion), re-rank with cross-encoder, keep top `top_k` (Retrieval Planner default: `top_k=5`) for the Teaching Agent.

---

## 7. Safety & Validation Rules

- **Validation Agent** rejects: empty queries, queries under 3 characters, non-educational content (use a lightweight zero-shot classifier or keyword/topic filter — not full LLM generation).
- **Safety Agent (query-side)** rejects: queries requesting harmful, violent, sexual, or clearly out-of-scope-for-minors content. Age-appropriate framing based on `grade` metadata from student session.
- **Safety Agent (response-side)** re-checks the final draft answer before it reaches the student, independent of the query-side check (a safe query can still produce an unsafe answer if source material is misused).
- Both Safety Agent passes must log flagged content to `interaction_logs` with `flagged: true` for later review — never silently drop without logging.

---

## 8. Fact Verification Logic

- For every sentence in the Teaching Agent's draft that makes a factual claim, check whether it can be traced to at least one `cited_chunk_id`'s text (semantic similarity between claim sentence and source chunk text, threshold `ASSUMPTION: 0.6 cosine similarity` using the same embedding model as §2 — no need for a second model).
- Claims that fail this check go into `unsupported_claims`.
- On failure, Supervisor triggers **one** Teaching Agent retry with an explicit instruction: "Only use the following verified source text, do not add any fact not present in it: {chunks}."
- If retry still fails verification, strip the unsupported sentences from the final answer rather than blocking the response entirely, and lower the confidence score accordingly.

---

## 9. File / Folder Structure

```
teaching-robot/
├── .env                          # gitignored — API keys, Mongo URI
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app/
│   ├── main.py                   # FastAPI app entrypoint
│   ├── config.py                 # env loading, constants (chunk size, thresholds)
│   ├── api/
│   │   ├── routes_query.py       # POST /query endpoint
│   │   └── routes_ingest.py      # POST /ingest endpoint (admin/internal)
│   ├── agents/
│   │   ├── supervisor_agent.py
│   │   ├── validation_agent.py
│   │   ├── safety_agent.py
│   │   ├── retrieval_planner_agent.py
│   │   ├── curriculum_rag_agent.py
│   │   ├── teaching_agent.py
│   │   ├── fact_verification_agent.py
│   │   └── response_agent.py
│   ├── models/
│   │   ├── schemas.py             # all Pydantic models from §5.2
│   │   └── db_models.py           # Mongo document shapes
│   ├── db/
│   │   ├── mongo_client.py        # async motor client, is-not-None patterns
│   │   └── chroma_client.py       # Chroma collection setup, filters
│   ├── retrieval/
│   │   ├── hybrid_search.py       # vector + BM25 + RRF fusion
│   │   ├── reranker.py            # cross-encoder re-ranking
│   │   └── bm25_index.py          # in-memory BM25 per subject
│   ├── ingestion/
│   │   ├── extract_text.py
│   │   ├── chunker.py
│   │   ├── embed_and_store.py
│   │   └── versioning.py
│   └── utils/
│       ├── logging_config.py
│       └── llm_client.py          # Groq client wrapper, flat-param enforcement helper
├── data/
│   └── curriculum_raw/{grade}/{subject}/
├── tests/
│   ├── test_agents/
│   ├── test_retrieval/
│   └── test_ingestion/
└── scripts/
    ├── run_ingestion.py
    └── seed_curriculum_config.py
```

---

## 10. API Contract (FastAPI)

### `POST /query`
```json
// Request
{
  "session_id": "str",
  "student_query": "str",
  "grade": "int",
  "subject": "str"
}
// Response: ResponsePayload (see §5.2)
```

### `POST /ingest`
```json
// Request (multipart form)
{
  "file": "<pdf/doc file>",
  "grade": "int",
  "subject": "str",
  "chapter": "str",
  "curriculum_version": "str"
}
// Response
{
  "chunks_created": "int",
  "curriculum_version": "str",
  "status": "success | error"
}
```

---

## 11. Implementation Phases

**Phase 1 — Foundation**
- MongoDB + ChromaDB setup, schemas from §5.
- Ingestion pipeline (§4) end-to-end for one sample subject/grade.
- No agents yet — just prove chunking → embedding → storage → retrieval works.

**Phase 2 — Core Agent Pipeline**
- Implement Supervisor, Validation, Retrieval Planner, Curriculum RAG, Teaching agents.
- Wire the sequence from §3.2 without Safety/Fact Verification yet.
- Get a query end-to-end returning a cited answer.

**Phase 3 — Safety & Verification Layer**
- Add Safety Agent (both passes), Fact Verification Agent.
- Add retry logic and confidence scoring.

**Phase 4 — Hardening**
- Hybrid retrieval (BM25 + RRF) if Phase 2 used vector-only as a placeholder.
- Cross-encoder re-ranking.
- Logging, `interaction_logs`, admin review tooling.

**Phase 5 — Testing & Calibration**
- Empirically tune thresholds in §6.3 and §8 using a labeled test set of curriculum Q&A pairs.
- Load testing on FastAPI async endpoints.

---

## 12. Known Pitfalls (from prior project experience — avoid repeating)

- **AgentScope v1.x**: all agent calls are async; do not write blocking/sync calls into agent methods, it breaks the orchestration loop silently.
- **Groq/LLaMA tool calls**: never pass nested JSON objects or arrays directly as a tool parameter type — flatten or stringify them first, or the tool call will fail or the model will hallucinate parameters.
- **MongoDB checks**: always use `if document is not None:`, never `if document:` — a valid chunk with empty-ish fields can evaluate as falsy and get silently skipped.
- **API keys**: never print, log, or paste full key values anywhere, including in this document's future revisions or in agent debug output.

---

## 13. Explicit Instructions for the Coding Agent

1. Implement Phase 1 and Phase 2 first; do not build Phase 3+ features until Phase 2 passes manual end-to-end testing.
2. Do not introduce additional agents beyond the 8 listed in §3.1 without flagging it as a proposed change first.
3. Do not substitute the tech stack in §2 (e.g., swapping ChromaDB for Pinecone, or Groq for OpenAI) without explicit instruction — these are locked decisions.
4. Where this document says `ASSUMPTION`, implement it as specified but leave the parameter as a named constant in `config.py` so it can be tuned later without code changes.
5. All new modules must have at least one corresponding test in `tests/` before being considered complete.
6. Do not fabricate curriculum content, sample data, or citations when writing tests — use clearly-marked placeholder/mock data (e.g., `"MOCK_CHUNK_TEXT_FOR_TESTING"`) so it's never confused with real curriculum content.
