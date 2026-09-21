from .student import router as student_router
from .courses import router as courses_router
from .attention import router as attention_router
from .transcription import router as transcription_router
from .assessment import router as assessment_router
from .gamification import router as gamification_router
from .report import router as report_router
from .content import router as content_router          # ← NEW
from .crs import router as crs_router                   # ← Phase 11 (NeuroLearn-MCL)
from .research import router as research_router

__all__ = [
    "student_router",
    "courses_router",
    "attention_router",
    "transcription_router",
    "assessment_router",
    "gamification_router",
    "report_router",
    "content_router",                                  # ← NEW
    "crs_router",                                       # ← Phase 11 (NeuroLearn-MCL)
    "research_router",
]
