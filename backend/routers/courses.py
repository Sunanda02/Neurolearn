"""
============================================================
ROUTER: Courses — Course listing, details, video links
Endpoints:
    GET /api/courses
    GET /api/courses/{course_id}
    GET /api/courses/{course_id}/videos/{video_id}
============================================================
"""

from fastapi import APIRouter, HTTPException
from schemas.models import Course, VideoLink
from data.database import get_all_courses, get_course

router = APIRouter(prefix="/api/courses", tags=["Courses"])


@router.get("/", response_model=list[Course])
async def list_courses():
    """Get all available courses with progress."""
    return get_all_courses()


@router.get("/{course_id}", response_model=Course)
async def get_course_detail(course_id: str):
    """Get a specific course with all video links."""
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/{course_id}/videos/{video_id}")
async def get_video_detail(course_id: str, video_id: str):
    """Get a specific video within a course."""
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    video = next(
        (v for v in course.get("video_links", []) if v["id"] == video_id),
        None,
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return {"course": course, "video": video}
