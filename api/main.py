from dotenv import load_dotenv
load_dotenv(override=True)

import sys
import os
import asyncio
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from models.llm_gateway import LLMGateway
from ai_teacher_robot.repositories.db_client import db_manager
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3

from services.ros2_bridge import ros2_bridge
from services.idle_expression_service import idle_expression_service

from api.routes_query import router as query_router
from api.routes_ingest import router as ingest_router
from api.errors import AppBaseException, app_exception_handler, unhandled_exception_handler


from services.redis_pubsub import redis_pubsub
from services.cache_service import cache_service
from services.correlation_middleware import CorrelationIDMiddleware
from services.alert_service import alert_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing FastAPI production lifespan singletons...")
    
    # Initialize Sentry Error Crash Reporting
    alert_service.init_sentry()

    # 1. Warm up LLMGateway
    gateway = LLMGateway()
    gateway.reload_configs()
    app.state.llm_gateway = gateway
    app.state.supervisor_v3 = ClassroomSupervisorAgentV3(name="SupervisorV3")
    
    # 2. Warm up MongoDB Connection Pool & Index Validation (Async Background Task)
    db = await db_manager.get_db()
    app.state.db = db
    async def _async_ensure_indexes():
        try:
            from ai_teacher_robot.repositories.user_repository import user_repository
            from ai_teacher_robot.repositories.curriculum_repository import CurriculumRepository
            await user_repository.ensure_indexes()
            await CurriculumRepository().ensure_indexes()
        except Exception as ie:
            logger.warning(f"DB index auto-validation notice: {ie}")
    asyncio.create_task(_async_ensure_indexes())
    
    # 3. Warm up Embedding Generator & Reranker Singletons (Threadpool Pre-load)
    from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
    from agents.retrieval.reranker import Reranker
    embedding_gen = EmbeddingGenerator()
    app.state.embedding_generator = embedding_gen

    async def _async_warmup_rag_models():
        try:
            logger.info("Pre-warming local RAG SentenceTransformer and Reranker models...")
            await asyncio.to_thread(embedding_gen._get_model)
            await asyncio.to_thread(Reranker()._get_model)
            logger.info("Local RAG models pre-warmed successfully.")
        except Exception as we:
            logger.warning(f"RAG model pre-warm notice: {we}")
    asyncio.create_task(_async_warmup_rag_models())

    # 4. Connect Redis Pub/Sub & Cache Backplane
    await cache_service.connect()
    await redis_pubsub.connect()
    app.state.redis_pubsub = redis_pubsub
    app.state.cache_service = cache_service
    
    # 5. Instantiate shared Supervisor Agent Singleton
    supervisor_v3 = ClassroomSupervisorAgentV3(name="SupervisorV3")
    app.state.supervisor_v3 = supervisor_v3
    
    # 6. Initialize Edu-Bot ROS2 Expression Hardware Bridge & Idle Service
    app.state.ros2_bridge = ros2_bridge
    await idle_expression_service.start()
    
    logger.info("FastAPI lifespan singletons, Redis backplane & Edu-Bot ROS2 services initialized.")
    yield
    
    logger.info("Shutting down FastAPI lifespan singletons & Edu-Bot ROS2 services...")
    await idle_expression_service.stop()
    await redis_pubsub.close()
    await cache_service.close()
    await db_manager.close()
    logger.info("FastAPI shutdown complete.")


app = FastAPI(
    title="AI Teaching Robot - V3 Platform Backend",
    description="FastAPI multi-agent platform backend serving Web UI, WebSockets streaming, and Humanoid Robot hardware.",
    version="3.0.0",
    lifespan=lifespan
)

# Correlation ID Context Tracking Middleware
app.add_middleware(CorrelationIDMiddleware)

# Register centralized exception handlers for domain reliability
app.add_exception_handler(AppBaseException, app_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Enable CORS for React Frontend and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(query_router)
app.include_router(ingest_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "3.0.0", "multi_agent_engine": "V3 Parallelized"}

@app.get("/readyz")
async def readiness_check():
    try:
        db = await db_manager.get_db()
        is_mongo_ok = db is not None
        return {
            "status": "ready" if is_mongo_ok else "degraded",
            "mongo_db": "connected" if is_mongo_ok else "disconnected",
            "in_memory_fallback": getattr(db_manager, "use_in_memory", True),
            "ros2_bridge": ros2_bridge.get_status()
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


