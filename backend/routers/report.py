"""
============================================================
ROUTER: Report — PDF report card generation & email
Endpoints:
    POST /api/report/generate    — generate PDF, return as download
    POST /api/report/email       — generate PDF + email to student
    GET  /api/report/email-status — check if email is configured
============================================================
"""

import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from services.report_generator import generate_report_card
from services.email_service import send_report_email, is_email_configured
import logging
logger = logging.getLogger("neurolearn.report_api")
import io


router = APIRouter(prefix="/api/report", tags=["Report"])


# ── Request / Response Models ──

class ReportAttention(BaseModel):
    avgScore: float = 0
    scoreHistory: list[float] = []
    totalSnapshots: int = 0
    attentivePercent: float = 70
    inattentivePercent: float = 20
    unfocusedPercent: float = 10
    avgEyeContact: float = 0.8
    avgBlinkRate: float = 16.0
    headPoseDistribution: dict = {}


class ReportAdaptiveResponse(BaseModel):
    performanceTrend: str = "stable"
    recommendedAction: str = "Keep learning!"
    nextAssessmentDifficulty: str = "medium"
    strengthAreas: list[str] = []
    weakAreas: list[str] = []


class ReportAssessment(BaseModel):
    sessionId: str = "N/A"
    score: float = 0
    totalPoints: int = 0
    earnedPoints: int = 0
    percentage: float = 0
    xpEarned: int = 0
    timeSpent: int = 0
    correctAnswers: int = 0
    totalQuestions: int = 0
    difficulty: str = "medium"
    message: str = ""
    nextDifficulty: str = "medium"
    suggestedTopics: list[str] = []
    adaptiveResponse: ReportAdaptiveResponse = ReportAdaptiveResponse()


class ReportStudent(BaseModel):
    name: str = "Student"
    email: str = ""
    id: str = "student_001"
    level: int = 1
    xp: int = 0


class ReportCourse(BaseModel):
    title: str = "Course"
    id: str = "course_001"


class ReportVideo(BaseModel):
    title: str = "Video"
    id: str = "video_001"
    duration: int = 0


class ReportTranscription(BaseModel):
    totalSegments: int = 0
    avgConfidence: float = 0.0


class GenerateReportRequest(BaseModel):
    student: ReportStudent = ReportStudent()
    course: ReportCourse = ReportCourse()
    video: ReportVideo = ReportVideo()
    assessment: ReportAssessment = ReportAssessment()
    behavioral_cue: ReportAttention = ReportAttention()
    transcription: ReportTranscription = ReportTranscription()


class EmailReportRequest(BaseModel):
    toEmail: str
    reportData: GenerateReportRequest


class EmailStatusResponse(BaseModel):
    configured: bool
    message: str


# ── Endpoints ──

@router.post("/generate")
async def generate_report(request: GenerateReportRequest):
    """
    Generate a PDF report card and return it as a downloadable file.
    """
    try:
        data = request.model_dump()
        data["generatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        pdf_bytes = generate_report_card(data)

        student_name = request.student.name.replace(" ", "_")
        filename = f"NeuroLearn_Report_{student_name}_{time.strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.post("/email")
async def email_report(request: EmailReportRequest):
    """
    Generate a PDF report card and email it to the specified address.
    """
    try:
        data = request.reportData.model_dump()
        data["generatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        pdf_bytes = generate_report_card(data)

        student_name = request.reportData.student.name.replace(" ", "_")
        filename = f"NeuroLearn_Report_{student_name}_{time.strftime('%Y%m%d')}.pdf"

        result = send_report_email(
            to_email=request.toEmail,
            student_name=request.reportData.student.name,
            course_title=request.reportData.course.title,
            score=request.reportData.assessment.percentage,
            pdf_bytes=pdf_bytes,
            filename=filename,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email report failed: {e}")
        raise HTTPException(status_code=500, detail=f"Email report failed: {str(e)}")


@router.get("/email-status", response_model=EmailStatusResponse)
async def email_status():
    """Check if email sending is configured."""
    configured = is_email_configured()
    return EmailStatusResponse(
        configured=configured,
        message="Email is configured and ready" if configured else "Set SMTP_USER and SMTP_PASSWORD in .env to enable email",
    )
