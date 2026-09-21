"""
============================================================
NEUROLEARN — Adaptive Learning Platform Backend
FastAPI Application Entry Point

Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs (Swagger UI)
============================================================
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from routers import (
    student_router,
    courses_router,
    attention_router,
    transcription_router,
    assessment_router,
    gamification_router,
    report_router,
    content_router,          # ← NEW: Auto Course Generator
    crs_router,               # ← Phase 11 (NeuroLearn-MCL): CRS read endpoints
    research_router,
)
from routers.auth import router as auth_router

# Import database seeding + Postgres init
from data.database import seed_database
from data.db import init_db
from services.attention_log_purge_scheduler import (
    attention_log_purge_loop,
    stop_attention_log_purge,
)

# Import ML models (for health check)
from ml import attention_detector, transcription_service, question_generator
from config.llm_config import LLM_CONFIG


# ── Lifespan: Startup & Shutdown ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    purge_stop_event: asyncio.Event | None = None
    purge_task: asyncio.Task | None = None

    # ── STARTUP ──
    logger.info("=" * 60)
    logger.info("  NEUROLEARN BACKEND — Starting Up")
    logger.info("=" * 60)

    # Create Postgres tables if they don't exist yet (replaces the old
    # TinyDB JSON file — see data/db.py, data/models_orm.py)
    init_db()

    from auth.security import JWT_SECRET
    if JWT_SECRET == "dev-only-insecure-secret-change-me":
        logger.warning(
            "JWT_SECRET is using the insecure default — set a real random "
            "value via the JWT_SECRET env var before deploying anywhere "
            "other than local dev."
        )

    # Seed global demo content (courses, daily challenges, notifications).
    # Student accounts are NOT seeded here — see scripts/seed_demo_accounts.py,
    # which creates them for real via POST /api/auth/signup.
    seed_database()

    purge_stop_event = asyncio.Event()
    purge_task = asyncio.create_task(attention_log_purge_loop(purge_stop_event))

    # Log ML model status
    logger.info(f"Behavioral Cue Model:     {'LIVE' if attention_detector.face_mesh else 'DUMMY'}")
    logger.info(f"Transcription Model: {'LIVE' if transcription_service.model else 'DUMMY'}")
    logger.info(
        f"Question Generator:  {'LIVE' if question_generator.provider else 'DUMMY'} "
        f"(provider={LLM_CONFIG.provider}, model={LLM_CONFIG.model})"
    )
    logger.info("=" * 60)
    logger.success("Backend ready! Docs at http://localhost:8000/docs")

    yield

    # ── SHUTDOWN ──
    logger.info("Shutting down — cleaning up resources...")
    await stop_attention_log_purge(purge_task, purge_stop_event)
    attention_detector.cleanup()
    logger.info("Shutdown complete.")


# ── Create App ──
app = FastAPI(
    title="NeuroLearn API",
    description=(
        "Adaptive Learning Platform Backend\n\n"
        "**ML Models:**\n"
        "- Behavioral Cue Detection (MediaPipe Face Mesh)\n"
        "- Video Transcription (OpenAI Whisper)\n"
        "- Question Generation (configurable LLM via Ollama)\n"
        "- Adaptive Difficulty Engine\n\n"
        "**Features:**\n"
        "- Student profiles with gamification (XP, levels, badges)\n"
        "- Course management with video links\n"
        "- Real-time behavioral-cue monitoring from webcam\n"
        "- Live video transcription\n"
        "- Adaptive assessments that adjust to student performance\n"
        "- Leaderboard, daily challenges, notifications\n"
        "- Auto Course Generator (web scraping, no paid API)\n"
    ),
    version="1.1.0",
    lifespan=lifespan,
)


# ── CORS ──
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ──
app.include_router(auth_router)        # ← NEW: signup/login/me
app.include_router(student_router)
app.include_router(courses_router)
app.include_router(attention_router)
app.include_router(transcription_router)
app.include_router(assessment_router)
app.include_router(gamification_router)
app.include_router(report_router)
app.include_router(content_router)     # ← NEW
app.include_router(crs_router)         # ← Phase 11 (NeuroLearn-MCL)
app.include_router(research_router)


# ── Health Check ──
@app.get("/", tags=["Health"])
async def root():
    """API root — basic info."""
    return {
        "name": "NeuroLearn API",
        "version": "1.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check with ML model status.
    """
    return {
        "status": "healthy",
        "version": "1.1.0",
        "models_loaded": {
            "attention_detector": attention_detector.face_mesh is not None,
            "transcription_whisper": transcription_service.model is not None,
            "question_generator_llm": question_generator.provider is not None,
            "adaptive_engine": True,
        },
    }


@app.get("/api", tags=["Health"])
async def api_overview():
    """List all available API endpoint groups."""
    return {
        "endpoints": {
            "student": {
                "GET /api/student/profile": "Get student profile",
                "POST /api/student/xp": "Award XP",
            },
            "courses": {
                "GET /api/courses": "List all courses",
                "GET /api/courses/{id}": "Get course details",
                "GET /api/courses/{id}/videos/{vid}": "Get video details",
            },
            "attention": {
                "POST /api/attention/snapshot": "Analyze camera frame",
                "GET /api/attention/history": "Get behavioral-cue logs",
                "GET /api/attention/dummy-snapshot": "Get dummy data (no camera)",
            },
            "transcription": {
                "GET /api/transcription/{video_id}": "Full transcript",
                "GET /api/transcription/{video_id}/live": "Segment at timestamp",
                "POST /api/transcription/chunk": "Transcribe audio chunk",
            },
            "assessment": {
                "POST /api/assessment/generate": "Generate adaptive quiz",
                "POST /api/assessment/answer": "Submit one protocol question response",
                "POST /api/assessment/submit": "Submit answers + get results",
                "GET /api/assessment/session/{id}": "Get session details",
                "GET /api/assessment/results/{student_id}": "Result history",
            },
            "gamification": {
                "GET /api/leaderboard": "Global leaderboard",
                "GET /api/challenges/daily": "Daily challenges",
                "GET /api/notifications": "Student notifications",
            },
            "content_discovery": {                                       # ← NEW
                "POST /api/content/discover": "Discover videos for a topic (scraping)",
                "GET /api/content/courses/auto": "List auto-generated courses",
                "GET /api/content/courses/auto/{course_id}": "Get auto course details",
                "POST /api/content/pipeline/full": "Full pipeline: discover + transcribe + assess",
            },
        }
    }


# ── Run directly ──
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    uvicorn.run("main:app", host=host, port=port, reload=debug)