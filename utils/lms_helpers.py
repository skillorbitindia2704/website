"""Merge structured LMS rows with legacy Course JSON for student classroom."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import url_for

from models.lms import CourseModule, CourseNote, LiveSession, LmsQuiz, QuizAttempt, RecordedSession


def _live_dict(row: LiveSession) -> Dict[str, Any]:
    return {
        "id": row.id,
        "legacy": False,
        "title": row.title,
        "description": row.description or "",
        "meet_url": row.meet_url or "",
        "scheduled_at": row.scheduled_at,
        "status": (row.status or "upcoming").lower(),
        "session_update": row.session_update or "",
    }


def _legacy_live(course) -> List[Dict[str, Any]]:
    lc = course.live_class or {}
    url = lc.get("url") if isinstance(lc, dict) else None
    if not url:
        return []
    return [
        {
            "id": None,
            "legacy": True,
            "title": "Live class",
            "description": "",
            "meet_url": url,
            "scheduled_at": None,
            "status": "upcoming",
            "session_update": lc.get("datetime") or "",
        }
    ]


def live_sessions_for_course(course) -> List[Dict[str, Any]]:
    rows = (
        LiveSession.query.filter_by(course_id=course.id)
        .order_by(LiveSession.scheduled_at.asc(), LiveSession.id)
        .all()
    )
    if rows:
        return [_live_dict(r) for r in rows]
    return _legacy_live(course)


def recorded_lessons_for_course(course) -> List[Dict[str, Any]]:
    rows = (
        RecordedSession.query.filter_by(course_id=course.id, is_visible=True)
        .order_by(RecordedSession.sort_order, RecordedSession.id)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "legacy": False,
                "title": r.title,
                "description": r.description or "",
                "url": url_for("courses.stream_lecture", lecture_id=r.id) if r.video_path else "",
                "visible": bool(r.is_visible),
            }
        )
    if out:
        return out
    for idx, v in enumerate(course.videos or []):
        if not isinstance(v, dict):
            continue
        u = v.get("url") or ""
        if not u:
            continue
        out.append(
            {
                "id": f"legacy_{idx}",
                "legacy": True,
                "title": v.get("title") or f"Session {idx + 1}",
                "description": "",
                "url": u,
                "visible": True,
            }
        )
    return out


def materials_for_course(course) -> List[Dict[str, Any]]:
    rows = (
        CourseNote.query.filter_by(course_id=course.id, is_visible=True)
        .order_by(CourseNote.sort_order, CourseNote.id)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "legacy": False,
                "title": r.title,
                "description": r.description or "",
                "file_path": r.file_path or "",
                "body": "",
                "kind": "file" if (r.file_path or "").strip() else "text",
            }
        )
    if out:
        return out
    for idx, n in enumerate(course.notes or []):
        if not isinstance(n, dict):
            continue
        out.append(
            {
                "id": f"legacy_note_{idx}",
                "legacy": True,
                "title": n.get("title") or f"Note {idx + 1}",
                "description": "",
                "file_path": "",
                "body": n.get("content") or "",
                "kind": "text",
            }
        )
    return out


def quizzes_for_course(course) -> List[Dict[str, Any]]:
    rows = (
        LmsQuiz.query.filter_by(course_id=course.id, is_published=True)
        .order_by(LmsQuiz.sort_order, LmsQuiz.id)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        qs = r.questions_json if isinstance(r.questions_json, list) else []
        out.append(
            {
                "id": r.id,
                "legacy": False,
                "title": r.title or "Quiz",
                "time_limit_seconds": r.time_limit_seconds or 0,
                "pass_percent": r.pass_percent or 60,
                "questions": qs,
            }
        )
    return out


def latest_attempt(user_id: int, quiz_id: int) -> Optional[QuizAttempt]:
    return (
        QuizAttempt.query.filter_by(user_id=user_id, quiz_id=quiz_id)
        .order_by(QuizAttempt.created_at.desc())
        .first()
    )


def build_lms_context(course, user_id: int) -> Dict[str, Any]:
    modules = (
        CourseModule.query.filter_by(course_id=course.id)
        .order_by(CourseModule.sort_order, CourseModule.id)
        .all()
    )
    live = live_sessions_for_course(course)
    recorded = recorded_lessons_for_course(course)
    materials = materials_for_course(course)
    quizzes = quizzes_for_course(course)
    attempts = {}
    for q in quizzes:
        qid = q["id"]
        if isinstance(qid, int) and qid > 0:
            att = latest_attempt(user_id, qid)
            if att:
                attempts[qid] = att
    now = datetime.utcnow()
    return {
        "modules": modules,
        "live_sessions": live,
        "recorded_lessons": recorded,
        "materials": materials,
        "quizzes": quizzes,
        "quiz_attempt_by_id": attempts,
        "now": now,
    }
