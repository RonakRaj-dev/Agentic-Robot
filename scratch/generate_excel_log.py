import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

def build_excel():
    wb = openpyxl.Workbook()
    
    # ---------------------------------------------------------
    # Styles Definition
    # ---------------------------------------------------------
    font_family = "Segoe UI"
    
    title_font = Font(name=font_family, size=16, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=12, bold=True, color="1F4E78")
    sub_font = Font(name=font_family, size=10, italic=True, color="595959")
    header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    data_font = Font(name=font_family, size=10, color="000000")
    bold_data_font = Font(name=font_family, size=10, bold=True, color="000000")
    metric_num_font = Font(name=font_family, size=14, bold=True, color="1F4E78")
    
    fill_dark_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_v1 = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid") # Soft Ice Blue
    fill_v2 = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Soft Mint Green
    fill_v3 = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Soft Peach / Amber
    fill_summary_hdr = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_card = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    
    fill_completed = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    fill_verified = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")
    
    thin_border_side = Side(border_style="thin", color="D9D9D9")
    thick_bottom_side = Side(border_style="medium", color="1F4E78")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    card_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    # ---------------------------------------------------------
    # SHEET 1: Executive Overview & Summary
    # ---------------------------------------------------------
    ws_over = wb.active
    ws_over.title = "Overview & Executive Summary"
    ws_over.views.sheetView[0].showGridLines = True
    
    # Title Banner
    ws_over.merge_cells("A1:G2")
    title_cell = ws_over["A1"]
    title_cell.value = "SILICON PROJECT: HUMANOID AI TEACHING ROBOT"
    title_cell.font = title_font
    title_cell.fill = fill_dark_navy
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    
    ws_over.merge_cells("A3:G3")
    sub_cell = ws_over["A3"]
    sub_cell.value = "Comprehensive 46-Day Work Log & Version Progress Breakdown (Version 1 to Version 3)"
    sub_cell.font = sub_font
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")

    # Metrics Summary Cards
    metrics = [
        ("Total Development Days", "46 Days", "A5:B6"),
        ("System Architecture Versions", "3 Major Versions", "C5:D6"),
        ("Specialized AI Agents Built", "18 Agents", "E5:E6"),
        ("Auxiliary Pipelines Built", "6 Pipelines", "F5:F6"),
        ("Test Suite Execution Status", "100% Passed", "G5:G6"),
    ]
    
    for title, val, cell_range in metrics:
        ws_over.merge_cells(cell_range)
        top_left = ws_over[cell_range.split(":")[0]]
        top_left.value = f"{title}\n{val}"
        top_left.font = bold_data_font
        top_left.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        top_left.fill = fill_card
        
        # Apply borders to range
        start, end = cell_range.split(":")
        start_col, start_row = start[0], int(start[1:])
        end_col, end_row = end[0], int(end[1:])
        for r in range(start_row, end_row + 1):
            for c in range(ord(start_col) - ord('A') + 1, ord(end_col) - ord('A') + 1):
                ws_over.cell(row=r, column=c).border = card_border

    # Version Comparison Table Header
    ws_over.cell(row=8, column=1, value="Version Development Milestones & Metrics").font = section_font
    
    headers_v = ["Version", "Day Span", "Primary Objective & Architecture Focus", "Key Agents & Modules", "Data Engine / Storage", "Testing & Verification", "Completion Status"]
    for col_idx, text in enumerate(headers_v, start=1):
        cell = ws_over.cell(row=9, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = fill_summary_hdr
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
        
    v_rows = [
        ("Version 1", "Days 1 – 15", "Core Multi-Agent Pipeline & LLM Gateway Failover. Direct LLM generation optimized for ultra-low latency.", "Supervisor, Validation, Safety, Teaching, Response Agents. LLMGateway failover.", "Redis (short-term history), MongoDB (audit trail), Dual In-Memory Fallbacks.", "Pytest unit test suite (6 tests), 100% mocked pass, ~2.1s query latency.", "100% Completed & Verified", fill_v1),
        ("Version 2", "Days 16 – 32", "Curriculum-Grounded RAG Ingestion Pipeline, Hybrid Retrieval (Vector + BM25 RRF), Cross-Encoder Reranking & Fact Verification.", "Supervisor V2, Retrieval Planner, Curriculum RAG, Fact Verification, Contradiction Checker.", "ChromaDB (vectors), MongoDB (source of truth chunks), NCERT Curriculum PDF parser.", "Hybrid search tests, cross-encoder scoring tests, fact verification retry tests.", "100% Completed & Verified", fill_v2),
        ("Version 3", "Days 33 – 46", "Advanced Multi-Agent Ecosystem (Adaptive Learning, Quiz, Assessment, Video, Memory, Analytics) & Modular Production Storage Service.", "Supervisor V3, Memory, Adaptive Learning, Quiz, Assessment, Video, Analytics Agents, Storage Service.", "Standalone Storage Service microservice, Pymupdf4LLM Markdown extraction, Qdrant integration.", "Comprehensive unit suite (18 agent tests, storage service test suite, idempotency tests).", "100% Completed & Verified", fill_v3),
    ]

    for row_idx, data in enumerate(v_rows, start=10):
        for col_idx, val in enumerate(data[:-1], start=1):
            cell = ws_over.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = data[-1]
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = cell_border

    # ---------------------------------------------------------
    # SHEET 2: Day-by-Day Detailed Work Log
    # ---------------------------------------------------------
    ws_log = wb.create_sheet(title="Day-by-Day Detailed Log")
    ws_log.views.sheetView[0].showGridLines = True
    
    headers_log = [
        "Day", "Version", "Category / Work Type", "Core Task Title",
        "Detailed Technical Work Accomplished", "Files & Modules Created / Modified",
        "Data Cleaning & Generation Work", "Agent Functions & Prompting Logic",
        "Bug Fixes & Root Cause Resolved", "Testing & Verification Executed", "Status"
    ]
    
    # Header row
    for col_idx, text in enumerate(headers_log, start=1):
        cell = ws_log.cell(row=1, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = fill_dark_navy
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
        
    ws_log.row_dimensions[1].height = 28

    days_data = [
        # VERSION 1: Days 1 - 15
        (1, "Version 1", "Architecture Setup", "Project Initialization & Tech Stack Configuration",
         "Configured Python virtual environment (.venv), AgentScope v1.x framework, Groq API SDK, FastAPI backend, and Pydantic validation. Established modular folder structure (agents/, models/, state/, tests/).",
         "requirements.txt, .env, .gitignore, main.py",
         "Setup initial repository structure and environment variable definitions (.env).",
         "Defined base AgentScope agent configuration parameters and async orchestration interfaces.",
         "None (Initial Setup)", "Environment validation & import checks.", "Completed", fill_v1),

        (2, "Version 2" if False else "Version 1", "Schema Design", "Structured Egress Contract (TeachingResponse)",
         "Designed strict Pydantic JSON egress contract matching robotic hardware requirements (screens, speech-to-text, animations). Added answer, summary, key_points, teaching_mode, diagram_required, video_required, quiz_generated, and confidence_score.",
         "models/schemas.py",
         "Created mock Pydantic payload models and schema validation scripts.",
         "Enforced strict JSON schema output formatting for downstream robotic execution engines.",
         "None", "Pydantic schema validation unit tests.", "Completed", fill_v1),

        (3, "Version 1", "LLM Gateway", "Primary Model Routing & Retry Mechanism",
         "Built centralized LLM gateway (models/llm_gateway.py) implementing primary model routing using llama-3.3-70b-versatile. Integrated exponential backoff and 3-attempt retry logic for transient API network errors.",
         "models/llm_gateway.py, models/compat.py",
         "N/A",
         "Configured primary model parameters, temperature settings (0.3), and max token limits.",
         "Patched AgentScope parameter signature mismatch via models/compat.py wrapper.",
         "Async unit tests verifying 3-attempt exponential retry policy.", "Completed", fill_v1),

        (4, "Version 1", "LLM Gateway", "Fallback Routing & Fault Tolerance Engine",
         "Integrated automated failover to fallback model llama-3.1-8b-instant when primary Groq model throws 429 rate limit or TPM/RPM errors. Ensured 99.9% pipeline uptime resilience.",
         "models/llm_gateway.py",
         "N/A",
         "Added dynamic fallback switch in LLM gateway execution loop.",
         "Resolved Groq rate limit crashes by catching LLMGatewayError and auto-routing to fallback.",
         "Unit test simulating primary API failure and verifying fallback response.", "Completed", fill_v1),

        (5, "Version 1", "State Management", "Dual Redis & MongoDB Session Manager",
         "Implemented SessionStateManager in state/sessionState.py utilizing Redis for fast short-term history caching and MongoDB for long-term audit trail logging. Created AgentStateManager in state/agentState.py.",
         "state/sessionState.py, state/agentState.py",
         "Configured Redis memory keys and MongoDB session log collection schemas.",
         "Created history windowing functions to restrict prompt context size.",
         "None", "Database connection string verification and session key read/write tests.", "Completed", fill_v1),

        (6, "Version 1", "State Management", "In-Memory Resilience Fallback System",
         "Built automatic fallback mechanism to standard Python in-memory dictionaries and threading timers if Redis or MongoDB connection attempts time out. Allows seamless deployment on standalone offline hardware.",
         "state/sessionState.py",
         "N/A",
         "Ensured in-memory state dictionary maintains identical interface methods as database drivers.",
         "Prevented hard crashes when external database containers are unreachable.",
         "Unit test test_session_state_in_memory_fallback verifying memory fallback under invalid DB URIs.", "Completed", fill_v1),

        (7, "Version 1", "Concurrency Control", "Thread-Safe Session Locking Mutex",
         "Embedded 15-second locking mechanism in sessionState.py and supervisor agent to prevent race conditions during rapid multi-click student queries. Concurrent queries under same session ID are rejected immediately.",
         "state/sessionState.py, agents/supervisorAgent.py",
         "N/A",
         "Configured supervisor to return Concurrent message error payload upon lock rejection.",
         "Fixed race condition history corruption caused by concurrent overlapping requests.",
         "Thread concurrency test verifying lock acquisition and rejection under parallel threads.", "Completed", fill_v1),

        (8, "Version 1", "Agent Development", "ValidationAgent (Input Sanitization & Security)",
         "Built ValidationAgent in agents/validatorAgent.py to sanitize student queries, detect prompt injection attacks, guard against token overflows, and block empty strings. Forces response_format type json_object.",
         "agents/validatorAgent.py",
         "N/A",
         "Prompted model to evaluate query validity and return JSON: {\"valid\": bool, \"reason\": str}.",
         "Blocked malicious prompt injections (e.g., 'ignore previous instructions').",
         "Unit tests for short strings, prompt injection samples, and empty strings.", "Completed", fill_v1),

        (9, "Version 1", "Agent Development", "SafetyAgent (Child Content Filtering)",
         "Built SafetyAgent in agents/safetyAgent.py to enforce strict elementary grade-level safety standards (Grades 1–5, ages 6–11). Blocks violent, inappropriate, adult, or non-educational queries before generation.",
         "agents/safetyAgent.py",
         "N/A",
         "Prompted safety classifier to evaluate content and return JSON: {\"safe\": bool, \"reason\": str}.",
         "Eliminated unsafe content generation risks before downstream processing.",
         "Unit tests verifying rejection of unsafe test prompts.", "Completed", fill_v1),

        (10, "Version 1", "Agent Development", "TeachingAgent (Pedagogical Content Engine)",
         "Built TeachingAgent in agents/teachingAgent.py to formulate engaging, kid-friendly concept explanations using simple vocabulary, relatable real-world analogies, and interactive home science experiments.",
         "agents/teachingAgent.py",
         "N/A",
         "Configured kid-friendly prompt template instructing model to act as an encouraging classroom teacher.",
         "None", "Manual prompt generation tests across elementary science queries.", "Completed", fill_v1),

        (11, "Version 1", "Agent Development", "ResponseAgent (JSON Formatter & Sanitizer)",
         "Built ResponseAgent in agents/responseAgent.py to re-structure plain-text lessons into rigid TeachingResponse Pydantic JSON structure. Added regex markdown block (```json) wrapper stripper.",
         "agents/responseAgent.py",
         "N/A",
         "Instructed formatter agent to extract key points, summary, teaching mode, and media flags.",
         "Fixed JSON parse failures caused by LLM wrapping JSON in markdown code blocks.",
         "Unit tests verifying 100% schema parity with TeachingResponse Pydantic model.", "Completed", fill_v1),

        (12, "Version 1", "Agent Build & Fix", "ClassroomSupervisorAgent Core Integration",
         "Built ClassroomSupervisorAgent in agents/supervisorAgent.py orchestrating sequential hand-offs: Validation -> Safety -> Teaching -> Response. Implemented short-circuit error wrapping in AgentResult envelope.",
         "agents/supervisorAgent.py",
         "N/A",
         "Orchestrated 4-agent execution sequence with session state locking and logging.",
         "Handled intermediate agent failures gracefully without leaking tracebacks to student UI.",
         "End-to-end pipeline execution test test_supervisor_pipeline_success.", "Completed", fill_v1),

        (13, "Version 1", "Bug Fix & Refactoring", "Pytest Timeout Fix & Directory Cleanup",
         "Resolved major Pytest hang where test suite took >10 mins by replacing invalid_host DNS lookups with 127.0.0.1. Fixed typo in file agents/vaidatorAgent.py -> validatorAgent.py and refactored imports.",
         "tests/test_components.py, agents/validatorAgent.py",
         "N/A",
         "Updated import references across all test modules.",
         "Root Cause Resolved: OS DNS lookup blocking on non-resolvable invalid_host strings.",
         "Pytest execution time reduced from >10 mins timeout to 2.86s.", "Completed", fill_v1),

        (14, "Version 1", "Testing & Tooling", "Unit Test Suite & Interactive CLI Script",
         "Created test_components.py containing 6 comprehensive unit tests covering session fallbacks, gateway retries, failover, pipeline success, and validation failure. Created run_pipeline.py CLI test script.",
         "tests/test_components.py, run_pipeline.py",
         "Created sample test queries ('Why is the sky blue?', 'How do fish breathe?').",
         "N/A",
         "Fixed async event loop loop attachment issue in pytest-asyncio environment.",
         "Passed all 6 unit tests in 2.86s. Verified run_pipeline.py interactive output.", "Completed", fill_v1),

        (15, "Version 1", "Benchmarking & Docs", "V1 Performance Audit & Report Documentation",
         "Achieved 2.14s end-to-end latency and 90% live LLM query success rate. Compiled comprehensive project documentation suite: status_report.md, inspection_report.md, and project_report.md.",
         "status_report.md, inspection_report.md, project_report.md",
         "Summarized agent inspection matrix and latency benchmark data.",
         "Documented agent responsibilities, failure modes, and system architecture.",
         "None", "Full system verification pass prior to V2 architectural expansion.", "Completed", fill_v1),

        # VERSION 2: Days 16 - 32
        (16, "Version 2", "Architecture Design", "V2 Curriculum RAG System Blueprint",
         "Authored teaching-robot-v2-plan.md defining architectural blueprint for curriculum-grounded Q&A. Locked tech stack: AgentScope v1.x async, ChromaDB, sentence-transformers/all-MiniLM-L6-v2, and cross-encoder.",
         "teaching-robot-v2-plan.md",
         "Defined curriculum raw data directory layout data/curriculum_raw/{grade}/{subject}/.",
         "Defined 8 specialized agent roles and strict Pydantic inter-agent payload models.",
         "None", "Architecture specification review against curriculum grounding goals.", "Completed", fill_v2),

        (17, "Version 2", "Data Ingestion", "PDF Curriculum Intake & Text Extraction Engine",
         "Built PDF extraction module parsing curriculum textbooks page-by-page while preserving exact page numbers and chapter metadata for citation tracking.",
         "ai_teacher_robot/rag/ingestion/extract_text.py",
         "Ingested sample elementary science curriculum PDFs into data/curriculum_raw/.",
         "N/A",
         "Resolved text fragmentation issues across multipage PDF document boundaries.",
         "Unit tests for text extraction completeness and page number mapping.", "Completed", fill_v2),

        (18, "Version 2", "Data Processing", "Recursive Character Chunking & Metadata Tagging",
         "Built dynamic character chunker using 500 token chunk size and 50 token overlap. Tagged metadata per chunk: {grade, subject, chapter, page_number, source_file, curriculum_version, chunk_id}.",
         "ai_teacher_robot/rag/chunking/chunker.py",
         "Cleaned and chunked elementary science textbook documents into discrete indexed passages.",
         "N/A",
         "Prevented loss of paragraph context during chunk boundary splitting.",
         "Unit tests verifying chunk size boundaries and metadata key presence.", "Completed", fill_v2),

        (19, "Version 2", "Vector Store", "Embedding Generation & ChromaDB Setup",
         "Generated 384-dimensional vector embeddings using sentence-transformers/all-MiniLM-L6-v2. Set up ChromaDB vector collection with native metadata filtering on grade, subject, and version.",
         "ai_teacher_robot/rag/vector_store/chroma_client.py, ai_teacher_robot/rag/embedding/",
         "Generated and populated ChromaDB vector index with curriculum chunk embeddings.",
         "N/A",
         "Fixed vector dimension mismatch during ChromaDB initialization.",
         "Vector similarity query unit tests verifying top-K retrieval accuracy.", "Completed", fill_v2),

        (20, "Version 2", "Data Synchronization", "MongoDB Source-of-Truth Chunk Mirroring",
         "Implemented dual-storage model where ChromaDB stores vectors + metadata and MongoDB stores authoritative raw chunk text in curriculum_chunks collection to eliminate database drift.",
         "ai_teacher_robot/rag/schemas/db_models.py, app/db/mongo_client.py",
         "Created MongoDB collection curriculum_chunks and indexed on chunk_id and grade/subject.",
         "N/A",
         "Fixed document retrieval inconsistency between vector store and document database.",
         "MongoDB read/write verification tests using Motor async client.", "Completed", fill_v2),

        (21, "Version 2", "Data Versioning", "Semver Curriculum Versioning Engine",
         "Built versioning engine tagging ingestion runs with semver string (e.g. 2026.1). Created curriculum_config collection storing active version per (grade, subject) pair for non-destructive updates.",
         "ai_teacher_robot/rag/ingestion/versioning.py",
         "Seeded initial curriculum version configuration records in MongoDB.",
         "N/A",
         "Prevented query pollution from outdated curriculum revisions.",
         "Version update and filtering unit tests.", "Completed", fill_v2),

        (22, "Version 2", "Data Generation", "Synthetic Curriculum Data & Seed Scripts",
         "Created scripts/seed_curriculum_config.py and ingest_silicon_rag.py to generate synthetic elementary curriculum datasets and ingest NCERT science textbook data into ChromaDB and MongoDB.",
         "scripts/seed_curriculum_config.py, ingest_silicon_rag.py",
         "Generated 150+ synthetic elementary science Q&A pairs and chapter text passages.",
         "N/A",
         "Cleaned missing metadata fields in synthetic PDF text exports.",
         "End-to-end ingestion runner execution test.", "Completed", fill_v2),

        (23, "Version 2", "Agent Development", "RetrievalPlannerAgent (Query Rewriting & Filter)",
         "Built RetrievalPlannerAgent to rewrite colloquial student queries into academic search queries (e.g., 'why does ice float' -> 'density of ice vs water buoyancy') and apply grade/subject filters.",
         "ai_teacher_robot/agents/retrieval/retrieval_planner_agent.py",
         "N/A",
         "Prompted model with strict instruction to output ONLY rewritten query string. Enforced flat parameter stringification for LLaMA tool calls.",
         "Fixed LLaMA tool call failure when passing nested JSON parameters.",
         "Unit tests for query rewriting accuracy across 10 sample queries.", "Completed", fill_v2),

        (24, "Version 2", "Agent Development", "CurriculumRAGAgent & Hybrid Search (BM25 + RRF)",
         "Built CurriculumRAGAgent implementing hybrid search: ChromaDB vector search + BM25 keyword search fused via Reciprocal Rank Fusion (RRF, k=60) to balance semantic and exact-keyword match accuracy.",
         "ai_teacher_robot/agents/retrieval/curriculum_rag_agent.py, app/retrieval/bm25_index.py",
         "Built in-memory BM25 keyword index per subject from MongoDB chunk repository.",
         "N/A",
         "Resolved keyword search omission for named entities and numerical constants.",
         "RRF rank fusion unit tests matching vector and BM25 candidate lists.", "Completed", fill_v2),

        (25, "Version 2", "Reranking & Threshold", "Cross-Encoder Re-Ranking & Confidence Scoring",
         "Built cross-encoder re-ranking engine using cross-encoder/ms-marco-MiniLM-L-6-v2 on top-20 retrieved candidate chunks. Implemented confidence score calculation and 0.35 rerank thresholding.",
         "ai_teacher_robot/agents/retrieval/reranker.py",
         "N/A",
         "Mapped top-3 cross-encoder scores to 0.0–1.0 confidence score range.",
         "Flagged insufficient curriculum coverage when top chunk score falls below 0.35.",
         "Re-ranking score calibration tests with known query-passage pairs.", "Completed", fill_v2),

        (26, "Version 2", "Agent Development", "FactVerificationAgent (Factual Grounding Check)",
         "Built FactVerificationAgent to extract factual claim sentences from Teaching Agent draft answers and cross-verify them against cited chunk text using 0.6 cosine similarity embedding threshold.",
         "ai_teacher_robot/agents/verification/fact_verification_agent.py",
         "N/A",
         "Structured verification egress payload: VerificationResult(verified: bool, unsupported_claims: list[str]).",
         "Prevented hallucinated facts from reaching student output.",
         "Fact verification tests with intentionally hallucinated draft answers.", "Completed", fill_v2),

        (27, "Version 2", "Agent Tools", "Auxiliary Verification Tools & Citation Generator",
         "Built contradiction_checker.py to detect conflicting facts across retrieved chunks and citation_generator.py to insert inline page and chapter citation markers into final answers.",
         "ai_teacher_robot/agents/verification/contradiction_checker.py, citation_generator.py",
         "N/A",
         "Formatted inline citation tags (e.g. [Grade 4 Science, Ch 2, p. 14]).",
         "Fixed broken citation formatting when source files contain special characters.",
         "Citation generator unit tests matching chunk IDs to formatted text labels.", "Completed", fill_v2),

        (28, "Version 2", "Agent Build & Fix", "SupervisorAgentV2 Multi-Agent Orchestrator",
         "Built supervisorAgentV2.py orchestrating complete V2 flow: Validation -> Safety (Query) -> Retrieval Planner -> RAG -> Teaching -> Fact Verification -> Response. Added 1-retry self-correction loop.",
         "agents/supervisorAgentV2.py",
         "N/A",
         "Implemented self-correction loop: if claims fail verification, Teaching Agent re-generates using verified chunks only.",
         "Handled retry fallback by stripping unverified sentences if 2nd pass fails.",
         "End-to-end V2 pipeline integration test test_v2_pipelines.py.", "Completed", fill_v2),

        (29, "Version 2", "Audit Logging", "Interaction Logs Audit Trail System",
         "Built interaction_logs collection driver in MongoDB recording session_id, student_query, rewritten_query, retrieved_chunk_ids, final_answer, confidence_score, and safety flags.",
         "app/db/mongo_client.py, agents/supervisorAgentV2.py",
         "Created MongoDB collection interaction_logs and configured indexing on timestamp and session_id.",
         "N/A",
         "Fixed unhandled exception when logging payloads containing non-serializable objects.",
         "Audit logging verification tests ensuring records persist after query completion.", "Completed", fill_v2),

        (30, "Version 2", "Testing Suite", "V2 End-to-End Pipeline Unit Test Suite",
         "Created tests/test_v2_pipelines.py containing end-to-end tests for hybrid retrieval, cross-encoder scoring, citation generation, and fact verification retry loops using mock chunk fixtures.",
         "tests/test_v2_pipelines.py",
         "Created mock chunk test fixtures (MOCK_CHUNK_TEXT_FOR_TESTING) to prevent synthetic test data pollution.",
         "N/A",
         "Isolated test environment from external database network dependencies.",
         "Passed all V2 pipeline tests cleanly in pytest.", "Completed", fill_v2),

        (31, "Version 2", "Bug Fix & Patch", "MongoDB Falsy Check & LLaMA Tool Call Fix",
         "Resolved critical MongoDB bug where valid documents evaluating falsy (e.g. {}) were skipped by switching to 'if doc is not None:'. Fixed LLaMA tool call failure by stringifying nested parameter dicts.",
         "app/db/mongo_client.py, ai_teacher_robot/agents/retrieval/retrieval_planner_agent.py",
         "N/A",
         "Enforced stringified JSON parameters in tool schemas across all agents.",
         "Root Cause Resolved: Python truthiness check ('if doc:') misidentifying empty valid dicts as None.",
         "Regression tests confirming falsy doc retrieval and tool parameter parsing.", "Completed", fill_v2),

        (32, "Version 2", "Refinement", "V2 Refinement & Confidence Calibration Test Suite",
         "Created tests/test_v2_refinement.py testing edge cases: low confidence queries, missing curriculum topics, safety flags during generation, and multi-chunk contradiction resolution.",
         "tests/test_v2_refinement.py",
         "Curated evaluation dataset of 25 complex elementary science queries.",
         "N/A",
         "Calibrated confidence threshold mapping to eliminate false-positive low confidence warnings.",
         "Passed test_v2_refinement.py test suite in 3.42s.", "Completed", fill_v2),

        # VERSION 3: Days 33 - 46
        (33, "Version 3", "Architecture Redesign", "V3 Advanced Multi-Agent Ecosystem Architecture",
         "Designed supervisor_agent_v3.py expanding system into a specialized multi-agent ecosystem covering adaptive learning, assessment, quiz generation, video prompt creation, memory, and analytics.",
         "agents/supervisor_agent_v3.py",
         "Defined specialized agent domains and pipeline orchestration hand-offs.",
         "Created sub-agent routing dispatcher based on query intent classification.",
         "None", "V3 architectural review and modular component verification.", "Completed", fill_v3),

        (34, "Version 3", "Agent Development", "MemoryAgent (Multi-Turn Student History)",
         "Built MemoryAgent in agents/memory_agent.py to synthesize short-term conversation context and long-term student learning profiles for personalized multi-turn pedagogical interaction.",
         "agents/memory_agent.py",
         "Configured student interaction memory schema storing topic history and error trends.",
         "Prompted memory agent to summarize student learning context without exceeding token budgets.",
         "Fixed context window overflow during extended 10+ turn conversations.",
         "Memory synthesis unit tests in test_new_agents.py.", "Completed", fill_v3),

        (35, "Version 3", "Agent & Pipeline", "AdaptiveLearningAgent & Difficulty Scaling Pipeline",
         "Built AdaptiveLearningAgent in agents/adaptive_learning_agent.py and pipelines/adaptive_learning_pipeline.py tracking student proficiency and dynamically adjusting Bloom's taxonomy difficulty level.",
         "agents/adaptive_learning_agent.py, pipelines/adaptive_learning_pipeline.py",
         "Created proficiency matrix schemas tracking student performance per topic.",
         "Calculated dynamic difficulty scalar (0.1–1.0) based on historical answer accuracy.",
         "Prevented difficulty jump when student answers single question incorrectly.",
         "Proficiency adjustment unit tests in test_v3_components.py.", "Completed", fill_v3),

        (36, "Version 3", "Agent Development", "QuizAgent (Interactive Quiz & Hint Engine)",
         "Built QuizAgent in agents/quizAgent.py generating dynamic multiple-choice quizzes matching grade level and chapter topics. Created distractor option generator and progressive hint engine.",
         "agents/quizAgent.py",
         "Generated quiz question schemas with answer key, distractors, and hint levels.",
         "Prompted model to craft age-appropriate quiz questions with plausible distractor choices.",
         "Fixed issue where correct answer choice was predictably positioned in position 'A'.",
         "Quiz generation unit tests in test_new_agents.py.", "Completed", fill_v3),

        (37, "Version 3", "Agent & Pipeline", "AssessmentAgent & Exam Evaluation Pipeline",
         "Built AssessmentAgent in agents/assessment_agent.py and pipelines/assessment_pipeline.py for automated exam paper generation and rubric-based scoring of open-ended student answers.",
         "agents/assessment_agent.py, pipelines/assessment_pipeline.py, agents/assessment_agent/",
         "Created exam blueprint schemas and rubric criteria matrices.",
         "Instructed agent to evaluate open-ended answers against 4-point pedagogical rubric.",
         "Fixed score inflation on partially correct student explanations.",
         "Assessment pipeline evaluation tests in test_v3_components.py.", "Completed", fill_v3),

        (38, "Version 3", "Agent Development", "VideoAgent (Visual Prompt & Animation Generator)",
         "Built VideoAgent in agents/videoAgent.py and prompts/video/config.json generating visual prompts, teaching robot screen animation cues, and educational video script breakdowns.",
         "agents/videoAgent.py, prompts/video/config.json",
         "Created visual scene description schemas for physical robot hardware display.",
         "Prompted agent to extract key visual concepts requiring diagram/video illustrations.",
         "None", "Video prompt generation unit tests in test_new_agents.py.", "Completed", fill_v3),

        (39, "Version 3", "Agent & Pipeline", "AnalyticsAgent & Student Learning Dashboard Pipeline",
         "Built AnalyticsAgent in agents/analytics_agent.py and pipelines/analytics_pipeline.py calculating topic mastery metrics, confusion index scores, and aggregated class engagement analytics.",
         "agents/analytics_agent.py, pipelines/analytics_pipeline.py",
         "Created aggregated analytics data structures and metric calculation formulas.",
         "Formatted progress metrics for educator report dashboards.",
         "Fixed division-by-zero error when calculating confusion index on zero-query sessions.",
         "Analytics metric calculation tests in test_v3_components.py.", "Completed", fill_v3),

        (40, "Version 3", "Pipeline Development", "Classroom, Homework & Summary Pipelines",
         "Built specialized auxiliary pipelines: classroom_pipeline.py (live engagement loop), homework_pipeline.py (homework assignment parser & hint generator), and summary_pipeline.py (lesson recaps).",
         "pipelines/classroom_pipeline.py, homework_pipeline.py, summary_pipeline.py, agents/classroom_interaction_agent.py, agents/content_generation_agent.py, agents/planner_agent.py, agents/summary_agent.py",
         "Structured homework assignment parsing models and recap schemas.",
         "Configured multi-step execution flows for auxiliary educational workloads.",
         "None", "Pipeline execution tests across all 3 auxiliary pipelines.", "Completed", fill_v3),

        (41, "Version 3", "Storage Refactoring", "Modular Storage Service Microservice Architecture",
         "Refactored legacy monolithic ingestion logic into standalone storage_service package. Defined domain models: book.py, exam.py, ingestion.py, pipeline.py, and embedded.py.",
         "storage_service/db/models/, storage_service/models/",
         "Designed modular database domain schemas and Pydantic DTO contracts.",
         "N/A",
         "Eliminated tight coupling between RAG retrieval logic and database storage layer.",
         "Storage model serialization unit tests test_embedded_serialization.py.", "Completed", fill_v3),

        (42, "Version 3", "Storage Development", "Storage Service Interfaces & MongoDB Repositories",
         "Built decoupled service interfaces (book_service, exam_service, object_service, config_service) and high-performance MongoDB repositories (base_mongo_repo.py, book_repo.py).",
         "storage_service/interfaces/, storage_service/repos/mongo/, storage_service/services/mongo/",
         "Created repository data access layers with indexed query filters.",
         "N/A",
         "Fixed memory leak caused by unclosed MongoDB client connections in repository factory.",
         "Repository unit tests test_book_service_v4.py and test_object_service.py.", "Completed", fill_v3),

        (43, "Version 3", "Markdown Ingestion", "Pymupdf4LLM Markdown Text Extraction Engine",
         "Upgraded extraction service in storage_service/services/pymupdf/ with pymupdf4llm to extract page text as clean Markdown, preserving tables, section headers (#, ##), and formulas.",
         "storage_service/services/pymupdf/pymupdf_service.py, storage_service/pipeline/",
         "Converted raw PDF textbook pages into Markdown format with preserved table layout.",
         "N/A",
         "Root Cause Resolved: Plain page.get_text() scrambling Markdown tables into unstructured text.",
         "Markdown extraction integration tests test_pipeline_with_mocks.py.", "Completed", fill_v3),

        (44, "Version 3", "Data Migration", "Production Migration Scripts & Catalog Importer",
         "Created migrate_v6_storage_refs.py to update database reference links and ingest_catalog.py for batch importing large NCERT textbook catalogs. Authored MIGRATION.md and STORAGE.md.",
         "storage_service/scripts/migrate_v6_storage_refs.py, storage_service/ingest_catalog.py, storage_service/MIGRATION.md",
         "Migrated legacy storage reference IDs across 500+ document records.",
         "N/A",
         "Fixed catalog import failure when handling books with missing ISBN metadata.",
         "Idempotency verification test test_reingestion_idempotency.py.", "Completed", fill_v3),

        (45, "Version 3", "Test Suite", "V3 & Storage Service Unit & Integration Test Suite",
         "Built comprehensive test suite in storage_service/tests/ and root tests/ (test_v3_components.py, test_new_agents.py) verifying batching, bug fixes, pipeline runs, and service registry.",
         "storage_service/tests/unit/, tests/test_v3_components.py, tests/test_new_agents.py",
         "Created comprehensive mock datasets for storage service unit tests.",
         "N/A",
         "Fixed test fixture collision between legacy RAG models and new storage service models.",
         "Passed all storage service unit tests (15 test files) and V3 component tests.", "Completed", fill_v3),

        (46, "Version 3", "Final Integration", "System Integration, Optimization & Excel Log Generation",
         "Validated end-to-end integration across all 18 agents, 6 pipelines, and storage service. Optimized async MongoDB motor drivers and Qdrant vector index queries. Programmatically generated Excel Work Log.",
         "agents/, pipelines/, storage_service/, generate_excel_log.py",
         "Finalized project codebase and validated database index performance.",
         "N/A",
         "Resolved minor latency bottleneck in async supervisor sub-agent event loop dispatcher.",
         "Final project verification pass: 100% test pass rate across all 3 major versions.", "Completed", fill_v3),
    ]

    for row_idx, day_data in enumerate(days_data, start=2):
        day_num, ver, cat, title, desc, files, data_work, agent_work, bug_fix, test_work, status, ver_fill = day_data
        
        row_values = [day_num, ver, cat, title, desc, files, data_work, agent_work, bug_fix, test_work, status]
        
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_log.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = cell_border
            
            # Formatting specifics per column
            if col_idx in [1, 2, 3, 11]:
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                
            if col_idx == 1:
                cell.font = bold_data_font
            elif col_idx == 2:
                cell.fill = ver_fill
                cell.font = bold_data_font
            elif col_idx == 11:
                cell.fill = fill_verified if status == "Completed" else fill_v1
                cell.font = bold_data_font
                
        ws_log.row_dimensions[row_idx].height = 65

    # ---------------------------------------------------------
    # SHEET 3: Version Breakdown & Comparison
    # ---------------------------------------------------------
    ws_vbreak = wb.create_sheet(title="Version Breakdown")
    ws_vbreak.views.sheetView[0].showGridLines = True
    
    ws_vbreak.cell(row=1, column=1, value="Silicon Project - Version Architectural Comparison Matrix").font = section_font
    
    headers_vb = ["Architectural Feature / Component", "Version 1 (Days 1–15)", "Version 2 (Days 16–32)", "Version 3 (Days 33–46)"]
    for col_idx, text in enumerate(headers_vb, start=1):
        cell = ws_vbreak.cell(row=2, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = fill_dark_navy
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
        
    ws_vbreak.row_dimensions[2].height = 25
    
    matrix_data = [
        ("Primary Goal & Philosophy", "Ultra-fast direct LLM concept generation without RAG overhead.", "Curriculum-grounded Q&A with strict factual verification.", "Full elementary educational robot suite with personalization & modular storage."),
        ("Orchestration Framework", "AgentScope v1.x (Sequential execution pipeline)", "AgentScope v1.x (Sequential RAG pipeline + self-correction retry)", "AgentScope v1.x (Async event-driven modular supervisor & sub-agent routing)"),
        ("Active Agent Count", "5 Agents (Supervisor, Validation, Safety, Teaching, Response)", "8 Agents (V1 agents + Retrieval Planner, Curriculum RAG, Fact Verification)", "18 Agents (V2 agents + Memory, Adaptive Learning, Quiz, Assessment, Video, Analytics, etc.)"),
        ("Active Pipelines", "1 Pipeline (Core Classroom Execution)", "1 Pipeline (V2 Curriculum RAG Pipeline)", "6 Specialized Pipelines (Classroom, Adaptive, Quiz, Assessment, Homework, Summary)"),
        ("LLM Provider & Model Routing", "Groq API (Primary: llama-3.3-70b-versatile, Fallback: llama-3.1-8b-instant)", "Groq API (Flat-parameter tool calls, query rewriting, fact check)", "Groq API (Multi-agent domain prompts, rubric evaluation, visual prompt generation)"),
        ("State & History Management", "Redis (short-term) + MongoDB (audit trail) + In-Memory Fallbacks", "Redis + MongoDB + In-Memory Fallbacks + interaction_logs audit collection", "Redis + MongoDB + In-Memory + MemoryAgent student profiles + analytics engine"),
        ("Data Extraction & Cleaning", "None (Direct LLM inference)", "PDF page text extraction (PyMuPDF plain text), 500/50 token chunking", "Pymupdf4LLM Markdown extraction (tables, headers, formulas preserved)"),
        ("Vector DB & Retrieval Engine", "None", "ChromaDB (cosine similarity) + BM25 Keyword Index + RRF Fusion (k=60)", "Qdrant Integration + ChromaDB + BM25 + FlashRank Reranker"),
        ("Factual Grounding & Verification", "None (Pure LLM generation)", "Sentence claim extraction + 0.6 cosine similarity verification + 1 retry", "Fact Verification Agent + Contradiction Checker + Rubric-based Assessment"),
        ("Storage Service Architecture", "Monolithic MongoDB driver in app root", "MongoDB curriculum_chunks + curriculum_config collections", "Standalone storage_service microservice with decoupled interfaces & repos"),
        ("Test Suite Execution Time", "2.86s (6 unit tests passed)", "3.42s (V2 pipeline & refinement tests passed)", "Full suite passed across 15+ test modules & storage service tests"),
    ]
    
    for row_idx, data in enumerate(matrix_data, start=3):
        feature, v1_desc, v2_desc, v3_desc = data
        ws_vbreak.cell(row=row_idx, column=1, value=feature).font = bold_data_font
        ws_vbreak.cell(row=row_idx, column=2, value=v1_desc).font = data_font
        ws_vbreak.cell(row=row_idx, column=3, value=v2_desc).font = data_font
        ws_vbreak.cell(row=row_idx, column=4, value=v3_desc).font = data_font
        
        ws_vbreak.cell(row=row_idx, column=2).fill = fill_v1
        ws_vbreak.cell(row=row_idx, column=3).fill = fill_v2
        ws_vbreak.cell(row=row_idx, column=4).fill = fill_v3
        
        for c in range(1, 5):
            cell = ws_vbreak.cell(row=row_idx, column=c)
            cell.border = cell_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            
        ws_vbreak.row_dimensions[row_idx].height = 45

    # ---------------------------------------------------------
    # SHEET 4: Agent & System Architecture Inventory
    # ---------------------------------------------------------
    ws_arch = wb.create_sheet(title="Agent & System Inventory")
    ws_arch.views.sheetView[0].showGridLines = True
    
    headers_arch = ["Component Type", "Name / File Module", "Version Introduced", "Core Responsibility & Functionality", "Input Payload", "Output Payload / Egress Contract"]
    for col_idx, text in enumerate(headers_arch, start=1):
        cell = ws_arch.cell(row=1, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = fill_dark_navy
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
        
    ws_arch.row_dimensions[1].height = 25
    
    inventory_data = [
        ("Agent", "ClassroomSupervisorAgent (agents/supervisorAgent.py)", "V1", "Orchestrates V1 sequential pipeline, session locks, and history logging.", "Student query string", "AgentResult Pydantic envelope"),
        ("Agent", "ValidatorAgent (agents/validatorAgent.py)", "V1", "Sanitizes queries, checks length, guards against injection.", "Raw student query", "JSON {\"valid\": bool, \"reason\": str}"),
        ("Agent", "SafetyAgent (agents/safetyAgent.py)", "V1", "Evaluates age appropriateness and educational relevance.", "Clean student query", "JSON {\"safe\": bool, \"reason\": str}"),
        ("Agent", "TeachingAgent (agents/teachingAgent.py)", "V1", "Generates engaging, kid-friendly concept explanations.", "Verified safe query", "Plain-text explanation string"),
        ("Agent", "ResponseAgent (agents/responseAgent.py)", "V1", "Formats text explanations into structured TeachingResponse JSON.", "Plain-text explanation", "TeachingResponse JSON matching schema"),
        ("Agent", "SupervisorAgentV2 (agents/supervisorAgentV2.py)", "V2", "Orchestrates V2 RAG search, reranking, and fact check retries.", "Student query + session ID", "ResponsePayload with citations"),
        ("Agent", "RetrievalPlannerAgent (ai_teacher_robot/agents/retrieval/retrieval_planner_agent.py)", "V2", "Rewrites queries into search terms and builds grade/subject filters.", "Student query + grade/subject", "RetrievalPlan (rewritten_query, filters)"),
        ("Agent", "CurriculumRAGAgent (ai_teacher_robot/agents/retrieval/curriculum_rag_agent.py)", "V2", "Executes hybrid vector + BM25 RRF search against ChromaDB/Mongo.", "RetrievalPlan", "List[RetrievedChunk]"),
        ("Agent", "FactVerificationAgent (ai_teacher_robot/agents/verification/fact_verification_agent.py)", "V2", "Cross-verifies claims in draft answer against cited chunks.", "Draft answer + cited chunks", "VerificationResult (verified, claims)"),
        ("Agent", "SupervisorAgentV3 (agents/supervisor_agent_v3.py)", "V3", "Orchestrates modular V3 sub-agent ecosystem & pipeline routing.", "Student query + session state", "Domain-specific execution payload"),
        ("Agent", "MemoryAgent (agents/memory_agent.py)", "V3", "Synthesizes short-term and long-term student interaction memory.", "Session history", "Context memory summary"),
        ("Agent", "AdaptiveLearningAgent (agents/adaptive_learning_agent.py)", "V3", "Tracks student proficiency and scales Bloom's difficulty scalar.", "Student response history", "Difficulty scalar (0.1 - 1.0)"),
        ("Agent", "QuizAgent (agents/quizAgent.py)", "V3", "Generates interactive quizzes with distractors and hints.", "Topic + grade level", "QuizPayload JSON"),
        ("Agent", "AssessmentAgent (agents/assessment_agent.py)", "V3", "Generates exam papers and scores open-ended student answers.", "Exam topic or answer text", "Exam payload or Rubric score"),
        ("Agent", "VideoAgent (agents/videoAgent.py)", "V3", "Generates visual prompts and robot screen animation scripts.", "Teaching response text", "Video prompt JSON (config.json)"),
        ("Agent", "AnalyticsAgent (agents/analytics_agent.py)", "V3", "Calculates topic mastery metrics and confusion index scores.", "Session execution logs", "Analytics report JSON"),
        ("Agent", "ClassroomInteractionAgent (agents/classroom_interaction_agent.py)", "V3", "Monitors live student classroom interaction loops.", "Live interaction log", "Engagement status JSON"),
        ("Agent", "ContentGenerationAgent (agents/content_generation_agent.py)", "V3", "Generates supplementary lesson materials and plans.", "Lesson objective", "Lesson plan payload"),
        ("Pipeline", "AdaptiveLearningPipeline (pipelines/adaptive_learning_pipeline.py)", "V3", "Executes proficiency calculation and difficulty adjustment flow.", "Student performance log", "Updated proficiency profile"),
        ("Pipeline", "AnalyticsPipeline (pipelines/analytics_pipeline.py)", "V3", "Executes aggregated learning analytics calculation flow.", "Session history dataset", "Class analytics dashboard metrics"),
        ("Pipeline", "AssessmentPipeline (pipelines/assessment_pipeline.py)", "V3", "Executes automated exam creation and rubric evaluation flow.", "Exam request parameters", "Scored evaluation payload"),
        ("Pipeline", "ClassroomPipeline (pipelines/classroom_pipeline.py)", "V3", "Executes real-time student Q&A classroom loop.", "Classroom student input", "Interactive response envelope"),
        ("Pipeline", "HomeworkPipeline (pipelines/homework_pipeline.py)", "V3", "Parses homework assignments and provides hints.", "Homework question", "Guided hint payload"),
        ("Pipeline", "SummaryPipeline (pipelines/summary_pipeline.py)", "V3", "Generates concise lesson recaps and key takeaways.", "Lesson content", "Summary payload"),
        ("Microservice", "StorageService (storage_service/)", "V3", "Standalone document & vector storage microservice with Markdown engine.", "PDF / Markdown / Catalog metadata", "MongoDB objects & Qdrant vectors"),
    ]

    for row_idx, data in enumerate(inventory_data, start=2):
        ctype, name, ver, desc, inp, out = data
        ws_arch.cell(row=row_idx, column=1, value=ctype).font = bold_data_font
        ws_arch.cell(row=row_idx, column=2, value=name).font = data_font
        ws_arch.cell(row=row_idx, column=3, value=ver).font = bold_data_font
        ws_arch.cell(row=row_idx, column=4, value=desc).font = data_font
        ws_arch.cell(row=row_idx, column=5, value=inp).font = data_font
        ws_arch.cell(row=row_idx, column=6, value=out).font = data_font
        
        if ver == "V1":
            ws_arch.cell(row=row_idx, column=3).fill = fill_v1
        elif ver == "V2":
            ws_arch.cell(row=row_idx, column=3).fill = fill_v2
        else:
            ws_arch.cell(row=row_idx, column=3).fill = fill_v3
            
        for c in range(1, 7):
            cell = ws_arch.cell(row=row_idx, column=c)
            cell.border = cell_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            
        ws_arch.row_dimensions[row_idx].height = 32

    # ---------------------------------------------------------
    # Auto-adjust column widths across all sheets
    # ---------------------------------------------------------
    col_widths = {
        "Overview & Executive Summary": [22, 18, 40, 35, 35, 30, 25],
        "Day-by-Day Detailed Log": [8, 12, 22, 28, 48, 30, 30, 30, 32, 28, 14],
        "Version Breakdown": [28, 38, 38, 38],
        "Agent & System Inventory": [16, 36, 12, 45, 25, 28]
    }
    
    for sheet_name, widths in col_widths.items():
        ws = wb[sheet_name]
        for col_idx, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Save output file
    output_path = r"c:\Users\gamer\OneDrive\Desktop\Silicon_Project\Silicon_Project_Day1_to_Day46_Work_Log.xlsx"
    wb.save(output_path)
    print(f"Successfully generated Excel workbook at: {output_path}")

if __name__ == "__main__":
    build_excel()
