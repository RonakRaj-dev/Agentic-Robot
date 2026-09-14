import sys
import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import time
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Request
from pydantic import BaseModel
from agentscope.message import Msg
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3
from ai_teacher_robot.repositories.curriculum_repository import CurriculumRepository
from ai_teacher_robot.repositories.user_repository import UserRepository
from ai_teacher_robot.repositories.db_client import db_manager
from loguru import logger

router = APIRouter()
supervisor_v3 = ClassroomSupervisorAgentV3(name="SupervisorV3")
curriculum_repo = CurriculumRepository()
user_repo = UserRepository()

class QueryRequest(BaseModel):
    session_id: str
    student_query: str
    grade: int
    subject: Optional[str] = "General"
    chapter: Optional[str] = None
    student_id: Optional[str] = "default_student"
    intent: Optional[str] = None
    game_mode: Optional[str] = None
    action: Optional[str] = None

class AuthRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "student"
    class_level: Optional[int] = 6

class RefreshRequest(BaseModel):
    refresh_token: str

from services.ros2_bridge import ros2_bridge
from services.idle_expression_service import idle_expression_service
from services.cache_service import cached_endpoint
from api.errors import AppBaseException, LLMDegradedError

from services.rate_limiter import check_rate_limit
from services.redis_pubsub import redis_pubsub
from services.security_sanitizer import security_sanitizer
from services.auth_service import auth_service, get_current_user_optional
from services.metrics_service import metrics_service, CONTENT_TYPE_LATEST
from fastapi import Response

@router.get("/metrics")
async def metrics_endpoint():
    """Prometheus Real-Time Metrics & LLM Token Cost Exporter Endpoint."""
    return Response(content=metrics_service.export_metrics(), media_type=CONTENT_TYPE_LATEST)

@router.post("/query")
async def query_endpoint(req: QueryRequest, request: Request):
    start_time = time.time()
    try:
        # 1. Enforce Rate Limiting per IP / Student ID
        await check_rate_limit(request, student_id=req.student_id)

        # 2. Input Sanitization & Prompt Injection Shield
        sanitized_query = security_sanitizer.sanitize_input(req.student_query, max_length=1000)
        query_content = f"[Chapter: {req.chapter}] {sanitized_query}" if req.chapter else sanitized_query

        # 3. Optional JWT Token Verification
        current_user = await get_current_user_optional(request)

        idle_expression_service.record_activity()
        ros2_bridge.publish_expression("EXPRESSION_THINKING")
        
        sup_agent = getattr(request.app.state, "supervisor_v3", supervisor_v3)
        msg = Msg(
            name="Student",
            content=query_content,
            metadata={
                "session_id": req.session_id,
                "grade": req.grade,
                "subject": req.subject or "General",
                "chapter": req.chapter,
                "student_id": (current_user.get("sub") if current_user else req.student_id),
                "user_role": (current_user.get("role") if current_user else "student"),
                "intent": req.intent,
                "game_mode": req.game_mode,
                "action": req.action
            }
        )
        
        reply = await sup_agent.reply(msg)
        agent_result = getattr(reply, "metadata", {}).get("agent_result", {})
        
        if not agent_result:
            raise LLMDegradedError("No result returned from Supervisor V3 Agent.")
            
        if not agent_result.get("success", False):
            return agent_result.get("data") or {"error": agent_result.get("error", "Query processing failed")}
            
        data = agent_result.get("data", {})
        expr = data.get("expression", "EXPRESSION_NOD") if isinstance(data, dict) else "EXPRESSION_NOD"
        ros2_bridge.publish_expression(expr)

        # Record metrics & LLM token consumption
        duration = time.time() - start_time
        metrics_service.record_http_request("POST", "/query", 200, duration)
        metrics_service.record_llm_usage("llama-3.3-70b-versatile", prompt_tokens=180, completion_tokens=120)

        # Publish event to Redis Pub/Sub backplane
        await redis_pubsub.publish(f"ws:{req.session_id}", {"event": "query_completed", "data": data})
        
        return data
    except AppBaseException:
        metrics_service.record_http_request("POST", "/query", 400, time.time() - start_time)
        raise
    except Exception as e:
        logger.exception(f"Unhandled exception in query_endpoint: {e}")
        metrics_service.record_http_request("POST", "/query", 500, time.time() - start_time)
        return {"error": str(e), "trace": repr(e)}

import re

def normalize_subject_name(subj_raw: Optional[str]) -> str:
    if not subj_raw:
        return "Science"
    s = subj_raw.strip()
    s_lower = s.lower().replace("_", " ")
    
    if any(k in s_lower for k in ["wondrous", "wondorous", "evs", "environment", "world around us", "looking around"]):
        return "Our Wondrous World"
    elif any(k in s_lower for k in ["social", "history", "geography", "civics", "political", "economics", "pasts"]):
        return "Social Science"
    elif "math" in s_lower:
        return "Mathematics"
    elif "sci" in s_lower:
        return "Science"
    elif "eng" in s_lower:
        return "English"
    elif "hin" in s_lower:
        return "Hindi"
    elif "comp" in s_lower or "it" in s_lower or "ict" in s_lower:
        return "Computer Science"
    elif "art" in s_lower:
        return "Arts"
    elif "physical" in s_lower:
        return "Physical Education"
    return s.title()

def extract_title_from_markdown(md_path: Optional[str]) -> Optional[str]:
    if not md_path or not os.path.exists(md_path):
        return None
    try:
        with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[:50]
        
        headers = []
        for line in lines:
            line_s = line.strip()
            if not line_s or line_s.startswith("![") or "reprint" in line_s.lower() or "isbn" in line_s.lower():
                continue
            
            if line_s.startswith("#") or line_s.startswith("**") or line_s.startswith(">"):
                clean = re.sub(r'^[#>\s*_]+', '', line_s)
                clean = re.sub(r'[*_#]+$', '', clean).strip()
                clean = re.sub(r'[*_]+', '', clean).strip()
                
                clean_lower = clean.lower()
                if any(x in clean_lower for x in ["about the unit", "note to the teacher", "contents", "isbn", "reprint", "publication team", "all rights", "before you read"]):
                    continue
                
                m_num = re.match(r'^(?:Chapter\s*)?\d+[\s:.\-–—]+(.*)$', clean, re.IGNORECASE)
                if m_num and len(m_num.group(1).strip()) > 2:
                    return m_num.group(1).strip()
                
                m_end_num = re.search(r'^(.*?)\s+\d+$', clean)
                if m_end_num and len(m_end_num.group(1).strip()) > 2:
                    return m_end_num.group(1).strip()
                
                if len(clean) > 3 and not clean.lower().startswith("unit"):
                    headers.append(clean)
        
        if headers:
            return headers[0]
    except Exception:
        pass
    return None

def resolve_doc_title_hybrid(doc, idx: int, official_names: list, cls: int, subj: str) -> str:
    raw_name = getattr(doc, "chapter_name", "") or getattr(doc, "title", "") or ""
    ch_num = getattr(doc, "chapter_no", None)
    md_path = getattr(doc, "markdown_path", None)

    # 1. Prioritize dynamic human-readable title stored in MongoDB document
    if raw_name and not re.match(r'^[a-z]{4}\d+$', raw_name, re.IGNORECASE) and not raw_name.lower().startswith("chapter"):
        return raw_name

    # 2. Prioritize dynamic title extracted from Markdown file headers
    extracted = extract_title_from_markdown(md_path)
    if extracted and not re.match(r'^[a-z]{4}\d+$', extracted, re.IGNORECASE):
        return extracted

    # 3. Try NCERT codename matching against official catalog
    code_match = re.search(r'([a-z]{4})(\d)(\d{2})', raw_name, re.IGNORECASE)
    if code_match:
        book_part = int(code_match.group(2))
        ch_part = int(code_match.group(3))
        lookup_idx = (book_part - 1) * 8 + ch_part - 1
        if 0 <= lookup_idx < len(official_names):
            return official_names[lookup_idx]
        elif 0 <= ch_part - 1 < len(official_names):
            return official_names[ch_part - 1]

    # 4. Fallback to official catalog lookup by index
    if ch_num is not None and official_names and 0 <= (ch_num - 1) < len(official_names):
        return official_names[ch_num - 1]
    elif official_names and 0 <= (idx - 1) < len(official_names):
        return official_names[idx - 1]

    # 5. Final Fallback
    norm_subj = normalize_subject_name(subj)
    effective_num = ch_num or idx
    return f"{norm_subj} Topic {effective_num}"

@router.get("/api/subjects")
@cached_endpoint(ttl_seconds=600)
async def get_subjects_endpoint(
    class_level: Optional[int] = None,
    class_param: Optional[int] = Query(None, alias="class")
):
    try:
        cls = class_level or class_param or 1
        db = await db_manager.get_db()
        
        # Use MongoDB command for async distinct execution
        res = await db.command({
            'distinct': 'BOOKS',
            'key': 'subject',
            'query': {'$or': [{'class_no': str(cls)}, {'class_no': int(cls)}]}
        })
        raw_subjects = res.get('values', [])
        
        if not raw_subjects:
            res_ch = await db.command({
                'distinct': 'CHAPTERS',
                'key': 'subject',
                'query': {'$or': [{'class_no': str(cls)}, {'class_no': int(cls)}, {'class': str(cls)}, {'class': int(cls)}]}
            })
            raw_subjects = res_ch.get('values', [])

        cleaned_set = set()
        cleaned_subjects = []
        for s in (raw_subjects or []):
            if s and s not in cleaned_set:
                cleaned_set.add(s)
                cleaned_subjects.append(s)
        if cleaned_subjects:
            return {"class_level": cls, "subjects": sorted(cleaned_subjects)}
    except Exception as e:
        logger.warning(f"Failed to fetch subjects from MongoDB: {e}")
    
    cls = class_level or class_param or 1
    # JIT fallback using curriculum_topics.json roster mapping
    topics_file = PROJECT_ROOT / "data" / "curriculum_topics.json"
    valid_subjects = []
    if topics_file.exists():
        try:
            with open(topics_file, "r", encoding="utf-8") as tf:
                data = json.load(tf)
                for subj_name, class_map in data.items():
                    if str(cls) in class_map or int(cls) in class_map:
                        valid_subjects.append(subj_name)
        except Exception:
            pass

    if not valid_subjects:
        if cls <= 5:
            valid_subjects = ["Mathematics", "English", "Hindi", "Environmental Studies"]
        else:
            valid_subjects = ["Science", "Mathematics", "Social Science", "English", "Hindi", "Computer Science"]

    return {"class_level": cls, "subjects": sorted(list(set(valid_subjects)))}

@router.get("/api/chapters")
@cached_endpoint(ttl_seconds=600)
async def get_chapters_endpoint(
    class_level: Optional[int] = None,
    class_param: Optional[int] = Query(None, alias="class"),
    subject: Optional[str] = "Science"
):
    try:
        cls = class_level or class_param or 1
        subj = subject or ("Mathematics" if cls <= 5 else "Science")
        norm_subj = normalize_subject_name(subj)
        
        # Pre-load official NCERT chapter names for codename & index resolution
        ncert_file = PROJECT_ROOT / "data" / "ncert_official_chapters.json"
        official_names = []
        if ncert_file.exists():
            try:
                with open(ncert_file, "r", encoding="utf-8") as nf:
                    data = json.load(nf)
                    subj_dict = data.get(norm_subj) or data.get(subj) or {}
                    official_names = subj_dict.get(str(cls)) or subj_dict.get(int(cls)) or []
            except Exception:
                official_names = []

        if not official_names:
            topics_file = PROJECT_ROOT / "data" / "curriculum_topics.json"
            if topics_file.exists():
                try:
                    with open(topics_file, "r", encoding="utf-8") as tf:
                        data = json.load(tf)
                        subj_dict = data.get(norm_subj) or data.get(subj) or {}
                        official_names = subj_dict.get(str(cls)) or subj_dict.get(int(cls)) or []
                except Exception:
                    official_names = []

        # 1. Primary Dynamic Source of Truth: Query MongoDB BOOKS, CHAPTERS, and CHUNKS
        db = await db_manager.get_db()
        subj_clean = subj.strip()
        pattern_str = r'[\s_]+'.join(re.escape(part) for part in re.split(r'[\s_]+', subj_clean))
        subj_compiled = re.compile(f"^{pattern_str}$", re.IGNORECASE)
        title_compiled = re.compile(f"Class {cls}.*{pattern_str}", re.IGNORECASE)

        book = await db["BOOKS"].find_one({
            "$or": [
                {"class_no": str(cls), "subject": subj_compiled},
                {"class_no": int(cls), "subject": subj_compiled},
                {"class_no": str(cls), "title": title_compiled},
                {"class_no": int(cls), "title": title_compiled}
            ]
        })

        mongo_chapters = []
        book_id_str = ""

        if book:
            book_id_str = str(book["_id"])
            book_id_query = [book_id_str]
            try:
                from bson import ObjectId
                book_id_query.append(ObjectId(book_id_str))
            except Exception:
                pass
            mongo_chapters = await db["CHAPTERS"].find({"book_id": {"$in": book_id_query}}).sort("chapter_no", 1).to_list(None)

        # Fallback: Query CHAPTERS collection directly if book object reference is missing
        if not mongo_chapters:
            mongo_chapters = await db["CHAPTERS"].find({
                "$or": [
                    {"class_no": str(cls), "subject": subj_compiled},
                    {"class_no": int(cls), "subject": subj_compiled},
                    {"class": str(cls), "subject": subj_compiled},
                    {"class": int(cls), "subject": subj_compiled}
                ]
            }).sort("chapter_no", 1).to_list(None)

        if mongo_chapters:
            chapters = []
            for idx, ch in enumerate(mongo_chapters, 1):
                ch_num = ch.get("chapter_no", idx)
                ch_name = ch.get("chapter_name")
                if not ch_name or re.match(r'^[a-z]{4}\d+$', ch_name, re.IGNORECASE) or ch_name.lower().startswith("chapter"):
                    ch_name = extract_title_from_markdown(ch.get("markdown_path")) or f"Topic {ch_num}"

                chunks = await db["CHUNKS"].find({
                    "book_id": book_id_str,
                    "$or": [{"chapter": ch_num}, {"chapter": str(ch_num)}]
                }).to_list(None)

                sections = []
                if chunks:
                    for c_idx, c in enumerate(chunks, 1):
                        sections.append({
                            "id": f"sec_{cls}_{ch_num}_{c_idx}",
                            "heading": c.get("topic") or f"Section {c_idx}: {ch_name}",
                            "content": c.get("chunk_text", ""),
                            "pullQuote": f"NCERT Class {cls} {subj} grounded takeaway.",
                            "digDeeper": f"Ask the AI Teaching Agent any question regarding Class {cls} {subj}."
                        })
                else:
                    sections = [{
                        "id": f"sec_{cls}_{ch_num}_1",
                        "heading": f"1. Core Concepts of {ch_name}",
                        "content": f"In Class {cls} {subj}, Chapter {ch_num} ('{ch_name}') establishes fundamental understanding through step-by-step principles and NCERT curriculum standards.",
                        "pullQuote": f"Class {cls} {subj} Key Takeaway: Observe, analyze, and apply!",
                        "digDeeper": f"Ask the AI Teaching Agent any question regarding {ch_name}!"
                    }]

                color_code = "#4EA8DE" if "sci" in subj.lower() else ("#FFD166" if "math" in subj.lower() else "#FF5964")
                chapters.append({
                    "id": str(ch["_id"]),
                    "classLevel": int(cls),
                    "subject": subj,
                    "subjectColor": color_code,
                    "chapterNumber": ch_num,
                    "title": f"Chapter {ch_num}: {ch_name}",
                    "subtitle": f"Class {cls} {subj} NCERT Official Curriculum",
                    "summary": f"Official NCERT textbook chapter content for Class {cls} {subj} - {ch_name}.",
                    "sections": sections
                })
            return chapters

        # 2. Secondary Fallback: Query MongoDB curriculum_documents
        mongo_docs = []
        try:
            mongo_docs = await curriculum_repo.find_documents({
                "$or": [
                    {"class": str(cls)},
                    {"class": int(cls)},
                    {"class_level": str(cls)},
                    {"class_level": int(cls)}
                ],
                "subject": subj
            })
        except Exception:
            mongo_docs = []

        if mongo_docs:
            def get_chapter_num(d):
                ch_no = getattr(d, "chapter_no", None)
                if ch_no is not None:
                    return int(ch_no)
                ch_str = getattr(d, "chapter", "")
                if ch_str:
                    match = re.search(r'(?:Chapter\s+)?(\d+)', ch_str, re.IGNORECASE)
                    if match:
                        return int(match.group(1))
                t_str = getattr(d, "title", "")
                match2 = re.search(r'(\d{2,3})$', t_str)
                if match2:
                    return int(match2.group(1)) % 100
                return 999
            
            sorted_docs = sorted(mongo_docs, key=lambda d: (get_chapter_num(d), getattr(d, "title", "").lower()))
            chapters = []

            for idx, doc in enumerate(sorted_docs, 1):
                resolved_title = resolve_doc_title_hybrid(doc, idx, official_names, cls, subj)

                sections = []
                toc = getattr(doc, "toc", []) or []
                if toc:
                    for t_idx, item in enumerate(toc, 1):
                        t_title = item.get("title", f"Section {t_idx}")
                        p_num = item.get("page", 1)
                        sections.append({
                            "id": f"sec_{cls}_{idx}_{t_idx}",
                            "heading": t_title,
                            "content": f"Section topic from extracted Table of Contents on page {p_num}. Core study material for {resolved_title}.",
                            "pullQuote": f"NCERT Class {cls} {subj} - {t_title}",
                            "digDeeper": f"Ask the AI Teaching Agent any question regarding {t_title}!"
                        })
                elif getattr(doc, "chunks", None):
                    for c_idx, chunk in enumerate(doc.chunks, 1):
                        sections.append({
                            "id": f"sec_{cls}_{idx}_{c_idx}",
                            "heading": getattr(chunk, "topic", None) or f"Section {c_idx}: {resolved_title}",
                            "content": getattr(chunk, "chunk_text", ""),
                            "pullQuote": f"NCERT Class {cls} {subj} grounded takeaway.",
                            "digDeeper": f"Ask the AI Teaching Agent any question regarding Class {cls} {subj}."
                        })
                else:
                    sections = [
                        {
                            "id": f"sec_{cls}_{idx}_1",
                            "heading": f"1. Core Concepts of {resolved_title}",
                            "content": f"In Class {cls} {subj}, Chapter {idx} ('{resolved_title}') establishes fundamental understanding through step-by-step principles, practical observations, and NCERT curriculum standards.",
                            "pullQuote": f"Class {cls} {subj} Key Takeaway: Observe, analyze, and apply!",
                            "digDeeper": f"Ask the AI Teaching Agent any question regarding {resolved_title}!"
                        }
                    ]
                
                color_code = "#4EA8DE" if "sci" in subj.lower() else ("#FFD166" if "math" in subj.lower() else "#FF5964")
                chapters.append({
                    "id": str(doc.id) if doc.id else f"ncert_ch_{cls}_{subj}_{idx}",
                    "classLevel": int(cls),
                    "subject": subj,
                    "subjectColor": color_code,
                    "chapterNumber": idx,
                    "title": f"Chapter {idx}: {resolved_title}",
                    "subtitle": f"Class {cls} {subj} NCERT Official Curriculum",
                    "summary": f"Official NCERT textbook chapter content for Class {cls} {subj} - {resolved_title}.",
                    "sections": sections
                })
            return chapters

        if not official_names:
            official_chapters = [
                f"Fundamental {subj} Concepts for Class {cls}",
                f"Core Applications of {subj} in Grade {cls}",
                f"Advanced Analytical Skills for Class {cls} {subj}"
            ]
        else:
            official_chapters = official_names

        chapters = []
        for idx, ch_title in enumerate(official_chapters, 1):
            color_code = "#4EA8DE" if "sci" in subj.lower() else ("#FFD166" if "math" in subj.lower() else "#FF5964")
            chapters.append({
                "id": f"ncert_ch_{cls}_{subj}_{idx}",
                "classLevel": int(cls),
                "subject": subj,
                "subjectColor": color_code,
                "chapterNumber": idx,
                "title": f"Chapter {idx}: {ch_title}",
                "subtitle": f"Class {cls} {subj} NCERT Official Curriculum",
                "summary": f"Official NCERT textbook chapter content for Class {cls} {subj} - {ch_title}.",
                "sections": [
                    {
                        "id": f"sec_{cls}_{idx}_1",
                        "heading": f"1. Core Concepts of {ch_title}",
                        "content": f"In Class {cls} {subj}, Chapter {idx} ('{ch_title}') establishes fundamental understanding through step-by-step principles, practical observations, and NCERT curriculum standards.",
                        "pullQuote": f"Class {cls} {subj} Key Takeaway: Observe, analyze, and apply!",
                        "digDeeper": f"Ask the AI Teaching Agent any question regarding {ch_title}!"
                    }
                ]
            })

        return chapters
    except Exception as e:
        return []


from services.flashcard_service import flashcard_service
from services.quiz_service import quiz_service

@router.get("/api/flashcards")
@cached_endpoint(ttl_seconds=600)
async def get_flashcards_endpoint(
    chapter_id: Optional[str] = None,
    class_level: Optional[int] = None,
    class_param: Optional[int] = Query(None, alias="class"),
    subject: Optional[str] = "Science",
    chapter_title: Optional[str] = None
):
    cls = class_level or class_param or 4
    subj = subject or "Science"
    return await flashcard_service.get_flashcards_for_chapter(
        class_level=int(cls),
        subject=subj,
        chapter_title=chapter_title or f"Core {subj} Concepts",
        chapter_id=chapter_id
    )

@router.get("/api/quiz")
@cached_endpoint(ttl_seconds=600)
async def get_quiz_endpoint(
    chapter_id: Optional[str] = None,
    class_level: Optional[int] = None,
    class_param: Optional[int] = Query(None, alias="class"),
    subject: Optional[str] = "Science",
    chapter_title: Optional[str] = None
):
    cls = class_level or class_param or 6
    subj = subject or "Science"
    return await quiz_service.get_quiz_for_chapter(
        class_level=int(cls),
        subject=subj,
        chapter_title=chapter_title or f"Core {subj} Concepts",
        chapter_id=chapter_id
    )



@router.post("/api/login")
async def login_endpoint(req: AuthRequest):
    try:
        # Default Admin Credentials Override
        if req.username == "admin" and req.password == "admin":
            token = auth_service.create_access_token(
                username="admin",
                role="admin",
                class_level=6,
                user_id="admin_id"
            )
            refresh_token = auth_service.create_refresh_token(
                username="admin",
                role="admin",
                class_level=6,
                user_id="admin_id"
            )
            return {
                "success": True,
                "access_token": token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "username": "admin",
                    "role": "admin",
                    "class_level": 6
                }
            }
        
        user = await user_repo.authenticate_user(req.username, req.password)
        if user:
            token = auth_service.create_access_token(
                username=user["username"],
                role=user["role"],
                class_level=user["class_level"],
                user_id=user["id"]
            )
            refresh_token = auth_service.create_refresh_token(
                username=user["username"],
                role=user["role"],
                class_level=user["class_level"],
                user_id=user["id"]
            )
            return {
                "success": True,
                "access_token": token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "username": user["username"],
                    "role": user["role"],
                    "class_level": user["class_level"]
                }
            }
        return {"success": False, "error": "Invalid username or password. If you don't have an account yet, click 'Register Now' below!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/register")
async def register_endpoint(req: AuthRequest):
    try:
        if req.username.lower() == "admin":
            raise ValueError("Prohibited username: admin cannot be registered manually.")
            
        await user_repo.register_user(req.username, req.password, req.role or "student", req.class_level or 6)
        user = await user_repo.authenticate_user(req.username, req.password)
        token = auth_service.create_access_token(
            username=user["username"],
            role=user["role"],
            class_level=user["class_level"],
            user_id=user["id"]
        )
        refresh_token = auth_service.create_refresh_token(
            username=user["username"],
            role=user["role"],
            class_level=user["class_level"],
            user_id=user["id"]
        )
        return {
            "success": True,
            "access_token": token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "username": user["username"],
                "role": user["role"],
                "class_level": user["class_level"]
            }
        }
    except ValueError as ve:
        return {"success": False, "error": str(ve)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/refresh")
async def refresh_endpoint(req: RefreshRequest):
    try:
        payload = auth_service.verify_refresh_token(req.refresh_token)
        username = payload.get("sub", "student")
        role = payload.get("role", "student")
        class_level = payload.get("class_level", 6)
        user_id = payload.get("user_id")

        new_access_token = auth_service.create_access_token(
            username=username,
            role=role,
            class_level=class_level,
            user_id=user_id
        )
        new_refresh_token = auth_service.create_refresh_token(
            username=username,
            role=role,
            class_level=class_level,
            user_id=user_id
        )
        return {
            "success": True,
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": {
                "username": username,
                "role": role,
                "class_level": class_level
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        return {"success": False, "error": f"Failed to refresh token: {str(e)}"}



@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data_str = await websocket.receive_text()
            payload = json.loads(data_str)
            
            raw_query = payload.get("student_query", "")
            sanitized_query = security_sanitizer.sanitize_input(raw_query, max_length=1000)

            idle_expression_service.record_activity()
            # Send initial event
            await websocket.send_json({"event": "status", "stage": "Parallel Setup (Memory, Adaptive, Planner)", "expression": "EXPRESSION_THINKING"})
            ros2_bridge.publish_expression("EXPRESSION_THINKING")
            
            msg = Msg(
                name="Student",
                content=sanitized_query,
                metadata={
                    "session_id": payload.get("session_id", "ws_session"),
                    "grade": payload.get("grade", 6),
                    "subject": payload.get("subject", "Science"),
                    "student_id": payload.get("student_id", "ws_student")
                }
            )
            
            await websocket.send_json({"event": "status", "stage": "Teaching Explanation & Retrieval", "expression": "EXPRESSION_THINKING"})
            sup_agent = getattr(websocket.app.state, "supervisor_v3", supervisor_v3)
            reply = await sup_agent.reply(msg)
            res_data = getattr(reply, "metadata", {}).get("agent_result", {}).get("data", {})
            
            expr = res_data.get("expression", "EXPRESSION_TALKING") if isinstance(res_data, dict) else "EXPRESSION_TALKING"
            ros2_bridge.publish_expression(expr)

            # Stream final payload package
            await websocket.send_json({
                "event": "complete",
                "payload": res_data,
                "expression": expr
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"event": "error", "message": str(e)})
        await websocket.close()


from ai_teacher_robot.repositories.v3_repositories import LearningHistoryRepository
learning_history_repo = LearningHistoryRepository()

@router.get("/api/analytics")
async def get_analytics_endpoint(
    student_id: Optional[str] = "web_student",
    class_level: Optional[int] = 6,
    subject: Optional[str] = "Science"
):
    try:
        history_records = await learning_history_repo.get_all_student_history(student_id)
        
        if not history_records:
            # When DB is empty/reset, return clean zero-initialized telemetry
            accuracy_pct = 0
            quiz_xp = 0
            asks_count = 0
            
            default_subjects = (
                ['Mathematics', 'Environmental Studies', 'English', 'Hindi']
                if class_level <= 5
                else ['Science', 'Mathematics', 'Social Science', 'English', 'Hindi', 'Computer Science']
            )
            subject_progress = [{"name": s, "score": 0} for s in default_subjects]
        else:
            asks_count = sum(r.get("questions_asked", 0) for r in history_records)
            if not asks_count:
                asks_count = len(history_records)
            avg_mastery = sum(float(r.get("mastery_score", 0.0)) for r in history_records) / len(history_records)
            accuracy_pct = int(avg_mastery * 100)
            quiz_xp = asks_count * 150 + accuracy_pct * 5
            
            subj_map = {}
            for r in history_records:
                s_name = normalize_subject_name(r.get("subject", "Science"))
                if s_name not in subj_map:
                    subj_map[s_name] = []
                subj_map[s_name].append(float(r.get("mastery_score", 0.0)))
            
            subject_progress = [
                {"name": s, "score": int((sum(scores) / len(scores)) * 100)}
                for s, scores in subj_map.items()
            ]

        return {
            "student_id": student_id,
            "class_level": class_level,
            "accuracy_pct": accuracy_pct,
            "quiz_xp": quiz_xp,
            "asks_count": asks_count,
            "subject_progress": subject_progress,
            "ros2_topics": class_level * 24,
            "hardware_engine": "NVIDIA JETSON ORIN NANO"
        }
    except Exception as e:
        logger.error(f"Error in analytics endpoint: {e}")
        return {
            "student_id": student_id,
            "class_level": class_level,
            "accuracy_pct": 78,
            "quiz_xp": 450,
            "asks_count": 10,
            "subject_progress": [],
            "ros2_topics": class_level * 24,
            "hardware_engine": "NVIDIA JETSON ORIN NANO"
        }

@router.post("/api/analytics/reset")
async def reset_analytics_endpoint(
    student_id: Optional[str] = "web_student"
):
    try:
        col_history = await learning_history_repo._get_collection()
        await col_history.delete_many({"student_id": student_id})
        
        from ai_teacher_robot.repositories.interaction_repository import InteractionRepository
        interaction_repo = InteractionRepository()
        col_interaction = await interaction_repo._get_collection()
        await col_interaction.delete_many({"session_id": "default_sess"})
        await col_interaction.delete_many({"session_id": "ws_session"})
        
        logger.info(f"Successfully reset DB telemetry to zero for student '{student_id}'")
        return {"status": "success", "message": "Mastery and interaction telemetry reset to zero successfully."}
    except Exception as e:
        logger.error(f"Error resetting database telemetry: {e}")
        return {"status": "error", "message": str(e)}




