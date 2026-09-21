
import os
import json
from typing import Optional
from tinydb import TinyDB, Query
from loguru import logger

DB_PATH = os.getenv("DB_PATH", "./data/neurolearn_db.json")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = TinyDB(DB_PATH)

# Tables
students_table = db.table("students")
courses_table = db.table("courses")
assessments_table = db.table("assessment_sessions")
results_table = db.table("assessment_results")
leaderboard_table = db.table("leaderboard")
challenges_table = db.table("daily_challenges")
notifications_table = db.table("notifications")
attention_logs_table = db.table("attention_logs")
transcripts_table = db.table("transcripts")
auto_courses_table = db.table("auto_courses")
# Phase 10 (NeuroLearn-MCL implementation spec): persistent CRS history.
# One record per assessment, holding every CRS component (P, A, I, T, C),
# the fused CRS, the selected difficulty, and the adaptive explanation —
# this is the durable replacement for AdaptiveEngine._history's in-memory
# dict (CR1/MJ4 in the peer review packet: history must survive a restart).
csr_history_table = db.table("csr_history")
# FIX (CR6, peer review packet): persistent store for webcam-monitoring
# consent, keyed by student_id, so /api/attention/snapshot has something
# to check before it ever touches a frame.
consent_table = db.table("consent")

def seed_database():
    """Populate database with initial dummy data if empty."""
    Q = Query()

    # ── Student ──
    if not students_table.search(Q.id == "student_001"):
        students_table.insert({
            "id": "student_001",
            "name": "Alex Johnson",
            "email": "alex@neurolearn.io",
            "avatar": "/placeholder-user.jpg",
            "level": 12,
            "xp": 4250,
            "xp_to_next_level": 5000,
            "streak": 7,
            "best_streak": 14,
            "total_courses_completed": 4,
            "total_watch_time": 1260,
            "joined_date": "2024-09-15",
            "rank": 23,
            "badges": [
                {"id": "b1", "name": "First Steps", "description": "Complete your first lesson", "icon": "👣", "earned": True, "earned_date": "2024-09-16", "rarity": "common"},
                {"id": "b2", "name": "Week Warrior", "description": "Maintain a 7-day streak", "icon": "⚔️", "earned": True, "earned_date": "2024-09-23", "rarity": "rare"},
                {"id": "b3", "name": "Perfect Score", "description": "Score 100% on an assessment", "icon": "💯", "earned": False, "rarity": "epic"},
                {"id": "b4", "name": "Speed Learner", "description": "Complete 5 lessons in one day", "icon": "🚀", "earned": False, "rarity": "epic"},
                {"id": "b5", "name": "Century Club", "description": "Earn 1000 XP", "icon": "💎", "earned": True, "earned_date": "2024-10-01", "rarity": "legendary"},
                {"id": "b6", "name": "Night Owl", "description": "Study past midnight", "icon": "🦉", "earned": True, "earned_date": "2024-10-05", "rarity": "common"},
                {"id": "b7", "name": "Quiz Master", "description": "Complete 50 quizzes", "icon": "🧠", "earned": False, "rarity": "legendary"},
                {"id": "b8", "name": "Social Butterfly", "description": "Join a study group", "icon": "🦋", "earned": False, "rarity": "rare"},
            ],
        })
        logger.info("Seeded student profile")

    # ── Courses ──
    if not courses_table.search(Q.id == "course_001"):
        courses = [
            {
                "id": "course_001",
                "title": "Introduction to React",
                "description": "Master the fundamentals of React including components, props, state, and hooks",
                "icon": "⚛️", "category": "Frontend", "difficulty": "Beginner",
                "total_videos": 8, "completed_videos": 5, "progress": 65, "estimated_hours": 6,
                "tags": ["React", "JavaScript", "Frontend"],
                "video_links": [
                    {"id": "v1", "title": "What is React? — Introduction & Setup", "url": "https://www.youtube.com/watch?v=SqcY0GlETPk", "duration": 720, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                    {"id": "v2", "title": "JSX & Components Deep Dive", "url": "https://www.youtube.com/watch?v=9YkUCRr3bVc", "duration": 890, "thumbnail": "", "order": 2, "completed": True, "watched_percent": 100},
                    {"id": "v3", "title": "Props & Data Flow", "url": "https://www.youtube.com/watch?v=PHaECbrKgs0", "duration": 650, "thumbnail": "", "order": 3, "completed": True, "watched_percent": 100},
                    {"id": "v4", "title": "State & useState Hook", "url": "https://www.youtube.com/watch?v=O6P86uwfdR0", "duration": 780, "thumbnail": "", "order": 4, "completed": True, "watched_percent": 100},
                    {"id": "v5", "title": "useEffect & Side Effects", "url": "https://www.youtube.com/watch?v=0ZJgIjIuY7U", "duration": 920, "thumbnail": "", "order": 5, "completed": True, "watched_percent": 100},
                    {"id": "v6", "title": "Event Handling & Forms", "url": "https://www.youtube.com/watch?v=dH6i3GurZW8", "duration": 640, "thumbnail": "", "order": 6, "completed": False, "watched_percent": 35},
                    {"id": "v7", "title": "Conditional Rendering", "url": "https://www.youtube.com/watch?v=4oCVDkb_peY", "duration": 540, "thumbnail": "", "order": 7, "completed": False, "watched_percent": 0},
                    {"id": "v8", "title": "Lists & Keys", "url": "https://www.youtube.com/watch?v=0sasRxl35_8", "duration": 480, "thumbnail": "", "order": 8, "completed": False, "watched_percent": 0},
                ],
            },
            {
                "id": "course_002",
                "title": "Advanced State Management",
                "description": "Redux, Context API, Zustand and modern state patterns",
                "icon": "🔄", "category": "Frontend", "difficulty": "Intermediate",
                "total_videos": 6, "completed_videos": 2, "progress": 42, "estimated_hours": 8,
                "tags": ["Redux", "Context API", "Zustand"],
                "video_links": [
                    {"id": "v9", "title": "Why State Management Matters", "url": "https://www.youtube.com/watch?v=CVpUuw9XSjY", "duration": 600, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                    {"id": "v10", "title": "Context API Fundamentals", "url": "https://www.youtube.com/watch?v=5LrDIWkK_Bc", "duration": 750, "thumbnail": "", "order": 2, "completed": True, "watched_percent": 100},
                    {"id": "v11", "title": "Redux Toolkit Setup", "url": "https://www.youtube.com/watch?v=9zySeP5vH9c", "duration": 880, "thumbnail": "", "order": 3, "completed": False, "watched_percent": 20},
                    {"id": "v12", "title": "Redux Thunk & Async", "url": "https://www.youtube.com/watch?v=93p3LxR9xfM", "duration": 920, "thumbnail": "", "order": 4, "completed": False, "watched_percent": 0},
                    {"id": "v13", "title": "Zustand — Lightweight Alternative", "url": "https://www.youtube.com/watch?v=_ngCLZ5Iz-0", "duration": 680, "thumbnail": "", "order": 5, "completed": False, "watched_percent": 0},
                    {"id": "v14", "title": "State Architecture Patterns", "url": "https://www.youtube.com/watch?v=HKU24nY8Hsc", "duration": 700, "thumbnail": "", "order": 6, "completed": False, "watched_percent": 0},
                ],
            },
            {
                "id": "course_003",
                "title": "Performance Optimization",
                "description": "React.memo, useMemo, code splitting, lazy loading, and profiling",
                "icon": "⚡", "category": "Frontend", "difficulty": "Advanced",
                "total_videos": 5, "completed_videos": 1, "progress": 28, "estimated_hours": 5,
                "tags": ["Performance", "Optimization", "React"],
                "video_links": [
                    {"id": "v15", "title": "React Performance Basics", "url": "https://www.youtube.com/watch?v=b1IQI4aJHLM", "duration": 800, "thumbnail": "", "order": 1, "completed": True, "watched_percent": 100},
                    {"id": "v16", "title": "React.memo & useMemo", "url": "https://www.youtube.com/watch?v=THL1OPn72vo", "duration": 700, "thumbnail": "", "order": 2, "completed": False, "watched_percent": 40},
                    {"id": "v17", "title": "Code Splitting & Lazy Loading", "url": "https://www.youtube.com/watch?v=JU6sl_yyZqs", "duration": 650, "thumbnail": "", "order": 3, "completed": False, "watched_percent": 0},
                    {"id": "v18", "title": "Profiler & DevTools", "url": "https://www.youtube.com/watch?v=LfEkP0bpFLc", "duration": 600, "thumbnail": "", "order": 4, "completed": False, "watched_percent": 0},
                    {"id": "v19", "title": "Real-world Optimization Case Study", "url": "https://www.youtube.com/watch?v=i8xbddI2Mg8", "duration": 900, "thumbnail": "", "order": 5, "completed": False, "watched_percent": 0},
                ],
            },
        ]
        for course in courses:
            courses_table.insert(course)
        logger.info(f"Seeded {len(courses)} courses")

    # ── Leaderboard ──
    if not leaderboard_table.all():
        entries = [
            {"rank": 1, "student_id": "s10", "name": "Priya Sharma", "avatar": "", "xp": 12500, "level": 24, "streak": 32, "courses_completed": 12},
            {"rank": 2, "student_id": "s11", "name": "Marcus Chen", "avatar": "", "xp": 11200, "level": 22, "streak": 28, "courses_completed": 10},
            {"rank": 3, "student_id": "s12", "name": "Sofia Reyes", "avatar": "", "xp": 10800, "level": 21, "streak": 15, "courses_completed": 11},
            {"rank": 4, "student_id": "s13", "name": "Aiden Okafor", "avatar": "", "xp": 9500, "level": 19, "streak": 20, "courses_completed": 9},
            {"rank": 5, "student_id": "s14", "name": "Emma Williams", "avatar": "", "xp": 8900, "level": 18, "streak": 12, "courses_completed": 8},
            {"rank": 23, "student_id": "student_001", "name": "Alex Johnson", "avatar": "", "xp": 4250, "level": 12, "streak": 7, "courses_completed": 4},
        ]
        for e in entries:
            leaderboard_table.insert(e)
        logger.info("Seeded leaderboard")

    # ── Daily Challenges ──
    if not challenges_table.all():
        challenges = [
            {"id": "dc1", "title": "Watch 30 minutes", "description": "Watch any video for 30 minutes", "xp_reward": 50, "type": "watch", "completed": True, "progress": 30, "target": 30},
            {"id": "dc2", "title": "Perfect Quiz", "description": "Score 100% on any quiz", "xp_reward": 100, "type": "quiz", "completed": False, "progress": 0, "target": 1},
            {"id": "dc3", "title": "Streak Keeper", "description": "Log in and study today", "xp_reward": 25, "type": "streak", "completed": True, "progress": 1, "target": 1},
            {"id": "dc4", "title": "Review Master", "description": "Review 3 completed lessons", "xp_reward": 75, "type": "review", "completed": False, "progress": 1, "target": 3},
        ]
        for c in challenges:
            challenges_table.insert(c)
        logger.info("Seeded daily challenges")

    # ── Notifications ──
    if not notifications_table.all():
        notifs = [
            {"id": "n1", "type": "achievement", "title": "Badge Earned!", "message": "You earned the Night Owl badge", "timestamp": "2 hours ago", "read": False, "icon": "🦉"},
            {"id": "n2", "type": "milestone", "title": "Level Up!", "message": "You reached Level 12", "timestamp": "1 day ago", "read": False, "icon": "⬆️"},
            {"id": "n3", "type": "challenge", "title": "Daily Challenge", "message": "New challenges available!", "timestamp": "3 hours ago", "read": True, "icon": "🎯"},
        ]
        for n in notifs:
            notifications_table.insert(n)
        logger.info("Seeded notifications")

    logger.success("Database seeding complete")



def get_student(student_id: str) -> Optional[dict]:
    Q = Query()
    results = students_table.search(Q.id == student_id)
    return results[0] if results else None


def update_student(student_id: str, updates: dict):
    Q = Query()
    students_table.update(updates, Q.id == student_id)


def get_all_courses() -> list[dict]:
    return courses_table.all()


def get_course(course_id: str) -> Optional[dict]:
    Q = Query()
    results = courses_table.search(Q.id == course_id)
    return results[0] if results else None


def save_assessment_session(session: dict):
    assessments_table.insert(session)


def get_assessment_session(session_id: str) -> Optional[dict]:
    Q = Query()
    results = assessments_table.search(Q.id == session_id)
    return results[0] if results else None


def save_assessment_result(result: dict):
    results_table.insert(result)


def get_student_results(student_id: str) -> list[dict]:
    Q = Query()
    return results_table.search(Q.student_id == student_id)


# ── Phase 10: persistent CRS history ───────────────────────────────────
#
# Design note: one record per assessment holds every component (P, A, I,
# T, C, CRS, difficulty, explanation), per the implementation spec's
# Phase 10 requirement ("Each assessment record must permanently store
# ... Performance ... Behavioral Cue ... Integrity ... Trend ... Complexity
# ... Final CRS ... Selected Difficulty ... Adaptive Explanation").
# The six "history" getters below (performance/attention/integrity/trend/
# complexity/crs) are projections over this ONE table rather than six
# separate tables — this avoids duplicating the same timestamp/student_id/
# assessment_id across six tables and keeps a single source of truth, while
# still satisfying Phase 11's "GET /<component>/history" endpoints, each of
# which just needs one field's time series.

def save_crs_record(record: dict) -> dict:
    """
    Persist one CRS computation. Expected keys (all required except
    `assessment_id`, which may be None for pre-assessment / initial-
    difficulty calls per get_initial_difficulty):

        student_id, assessment_id, timestamp,
        performance, behavioral_cue, integrity, trend, complexity,
        crs, difficulty, explanation

    Returns the same dict (with TinyDB's internal doc_id NOT included —
    callers should not depend on TinyDB internals).
    """
    required = {
        "student_id", "timestamp", "performance", "behavioral_cue", "integrity",
        "trend", "complexity", "crs", "difficulty", "explanation",
    }
    missing = required - record.keys()
    if missing:
        raise ValueError(f"save_crs_record missing required fields: {sorted(missing)}")

    record = dict(record)
    record.setdefault("assessment_id", None)
    csr_history_table.insert(record)
    logger.info(
        f"CRS persisted: student={record['student_id']} crs={record['crs']:.3f} "
        f"difficulty={record['difficulty']}"
    )
    return record


def get_crs_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    """Full CRS history (every component + fused score) for one student,
    ordered oldest-first. Pass `limit` to get only the most recent N."""
    Q = Query()
    records = csr_history_table.search(Q.student_id == student_id)
    records.sort(key=lambda r: r.get("timestamp", 0))
    return records[-limit:] if limit else records


def get_current_crs(student_id: str) -> Optional[dict]:
    """Most recent CRS record for a student, or None if they have no history yet."""
    history = get_crs_history(student_id)
    return history[-1] if history else None


def _component_history(student_id: str, component: str, limit: Optional[int]) -> list[dict]:
    """Shared implementation for the five per-component history getters
    below — each just projects one field out of the full CRS record,
    keeping {timestamp, assessment_id, value} so the frontend dashboards
    in Phase 13 can plot a simple time series without extra joins."""
    records = get_crs_history(student_id, limit=limit)
    return [
        {
            "timestamp": r["timestamp"],
            "assessment_id": r.get("assessment_id"),
            "value": r[component],
        }
        for r in records
    ]


def get_performance_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "performance", limit)


def get_behavioral_cue_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "behavioral_cue", limit)


def get_integrity_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "integrity", limit)


def get_trend_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "trend", limit)


def get_complexity_history(student_id: str, limit: Optional[int] = None) -> list[dict]:
    return _component_history(student_id, "complexity", limit)


def get_recent_scores_pct(student_id: str, limit: int = 5) -> list[float]:
    """
    Convenience helper for AdaptiveEngine: pulls recent assessment scores
    (as percentages) from the DURABLE `results_table`, not the in-memory
    dict. This is the one change needed in adaptive_engine.py to make
    Performance (P) and Trend (T) survive a server restart — see
    ml/adaptive_engine.py's updated `_scores_for()`.
    """
    results = get_student_results(student_id)
    results.sort(key=lambda r: r.get("timestamp", 0))
    scores = [r["score"] for r in results if "score" in r]
    return scores[-limit:]


def log_attention(log: dict):
    attention_logs_table.insert(log)


def get_attention_logs(video_id: str, student_id: str) -> list[dict]:
    Q = Query()
    return attention_logs_table.search(
        (Q.video_id == video_id) & (Q.student_id == student_id)
    )


# ── Consent (CR6 fix) ─────────────────────────────────────────
# NeuroLearn only ever stores derived behavioral_cue *scores*, never raw camera
# frames — frames are analyzed in-memory per request and discarded (see
# routers/attention.py). Consent governs whether those derived scores may
# be captured/logged at all.

def get_consent(student_id: str) -> Optional[dict]:
    Q = Query()
    return consent_table.get(Q.student_id == student_id)


def set_consent(record: dict) -> dict:
    Q = Query()
    consent_table.upsert(record, Q.student_id == record["student_id"])
    return record


def purge_expired_attention_logs() -> int:
    """
    Delete attention_logs rows older than the retention window the student
    consented to (default 30 days, see ConsentGrant.retention_days).
    Intended to be called on a scheduled job; also safe to call from a
    startup hook for the prototype. Returns the number of rows removed.
    """
    import datetime

    Q = Query()
    removed = 0
    for consent in consent_table.all():
        student_id = consent.get("student_id")
        retention_days = consent.get("retention_days", 30)
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
        ).isoformat()
        stale = attention_logs_table.search(
            (Q.student_id == student_id) & (Q.timestamp < cutoff)
        )
        if stale:
            attention_logs_table.remove(
                (Q.student_id == student_id) & (Q.timestamp < cutoff)
            )
            removed += len(stale)
    return removed


def get_leaderboard() -> list[dict]:
    return sorted(leaderboard_table.all(), key=lambda x: x.get("rank", 999))


def get_daily_challenges() -> list[dict]:
    return challenges_table.all()


def get_notifications(student_id: str = "student_001") -> list[dict]:
    return notifications_table.all()


# ── Auto Courses (add to database.py) ────────────────────────

from tinydb import Query as _Query

def save_auto_course(course_data: dict) -> None:
    """
    Persist an auto-generated course (from the scraping pipeline) to DB.
    Upserts by course_id to avoid duplicates on re-discover.
    """
    from data.database import auto_courses_table  # import the new table
    Q = _Query()
    course_id = course_data.get("course_id")
    existing = auto_courses_table.search(Q.course_id == course_id)
    if existing:
        auto_courses_table.update(course_data, Q.course_id == course_id)
    else:
        auto_courses_table.insert(course_data)


def get_auto_course(course_id: str) -> dict | None:
    """Retrieve a single auto-generated course by ID."""
    from data.database import auto_courses_table
    Q = _Query()
    results = auto_courses_table.search(Q.course_id == course_id)
    return results[0] if results else None


def get_all_auto_courses() -> list[dict]:
    """Return all auto-generated courses, newest first."""
    from data.database import auto_courses_table
    courses = auto_courses_table.all()
    return sorted(courses, key=lambda c: c.get("generated_at", 0), reverse=True)


def update_video_transcription_status(
    course_id: str,
    video_id: str,
    available: bool,
) -> None:
    """
    Mark a video inside an auto course as transcribed.
    Mutates the `videos` list inside the stored course document.
    """
    from data.database import auto_courses_table
    Q = _Query()
    course = get_auto_course(course_id)
    if not course:
        return
    updated_videos = []
    for v in course.get("videos", []):
        if v.get("id") == video_id:
            v["transcription_available"] = available
        updated_videos.append(v)
    auto_courses_table.update(
        {"videos": updated_videos},
        Q.course_id == course_id,
    )


def save_auto_course_to_courses(course_id: str) -> dict | None:
    """
    Convert an auto-generated course into the main courses table format.
    Upserts by id so the saved course appears in dashboard/video flows.
    """
    auto_course = get_auto_course(course_id)
    if not auto_course:
        return None

    def _to_title_case_difficulty(value: str) -> str:
        normalized = (value or "Intermediate").strip().lower()
        mapping = {
            "beginner": "Beginner",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
        }
        return mapping.get(normalized, "Intermediate")

    videos = auto_course.get("videos", [])
    converted_videos = []
    for idx, video in enumerate(videos, start=1):
        converted_videos.append({
            "id": video.get("id", f"auto_v_{idx}"),
            "title": video.get("title", f"Video {idx}"),
            "url": video.get("url", ""),
            "duration": int(video.get("duration", 0) or 0),
            "thumbnail": video.get("thumbnail", ""),
            "order": int(video.get("order", idx)),
            "completed": bool(video.get("completed", False)),
            "watched_percent": float(video.get("watched_percent", 0.0) or 0.0),
        })

    total_videos = len(converted_videos)
    completed_videos = sum(1 for v in converted_videos if v.get("completed"))
    total_seconds = sum(int(v.get("duration", 0) or 0) for v in converted_videos)
    estimated_hours = round(total_seconds / 3600, 1) if total_seconds > 0 else round(max(total_videos, 1) * 0.2, 1)
    progress = round((completed_videos / total_videos) * 100, 1) if total_videos > 0 else 0.0

    course_doc = {
        "id": auto_course.get("course_id", course_id),
        "title": auto_course.get("course_title", "Auto Course"),
        "description": auto_course.get("description", "Auto-generated course"),
        "icon": auto_course.get("icon", "🎓"),
        "category": auto_course.get("category", "Auto-Generated"),
        "difficulty": _to_title_case_difficulty(auto_course.get("difficulty", "Intermediate")),
        "total_videos": total_videos,
        "completed_videos": completed_videos,
        "progress": progress,
        "estimated_hours": max(0.1, estimated_hours),
        "tags": auto_course.get("tags", ["auto-generated"]),
        "video_links": converted_videos,
    }

    Q = Query()
    if courses_table.search(Q.id == course_doc["id"]):
        courses_table.update(course_doc, Q.id == course_doc["id"])
    else:
        courses_table.insert(course_doc)

    return course_doc
