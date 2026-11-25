"""영역 05 데스크 승인·출고 — API-05-01 ~ 03."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..models import Article, Region, User, ViewerQuestion
from ..security import desk_only
from ..sse import broker

router = APIRouter(prefix="/api/desk", tags=["05 데스크 승인·출고"])


class Decision(BaseModel):
    comment: str = ""
    urgent: bool = False         # 긴급 승인


@router.get("/articles", summary="API-05-01 승인 대기 목록")
def waiting(status: str = "SUBMITTED", db: Session = Depends(get_db), _: User = Depends(desk_only)):
    users = {u.user_id: u.name for u in db.query(User)}
    names = {r.region_code: r.name for r in db.query(Region)}
    q = db.query(Article).filter(Article.status.in_(status.split(",")))
    q = q.order_by(Article.submitted_at.asc()) if status == "SUBMITTED" else q.order_by(Article.article_id.desc())
    now = datetime.now()
    return [{"article_id": a.article_id, "reporter": users.get(a.reporter_id), "title": a.title, "status": a.status,
             "event_type": a.event_type, "urgent": bool(a.urgent), "region": a.region_code, "region_name": names.get(a.region_code),
             "submitted_at": a.submitted_at.strftime("%H:%M:%S") if a.submitted_at else None,
             "approved_at": a.approved_at.strftime("%H:%M:%S") if a.approved_at else None,
             "waiting_sec": int((now - a.submitted_at).total_seconds()) if a.submitted_at and a.status == "SUBMITTED" else None}
            for a in q.limit(100)]


@router.post("/articles/{article_id}/approve", summary="API-05-02 승인(출고)")
def approve(article_id: int, body: Decision = Decision(), db: Session = Depends(get_db), desk: User = Depends(desk_only)):
    a, q = services.approve(db, article_id, desk, body.comment, body.urgent)
    return {"article_id": a.article_id, "status": a.status, "urgent": a.urgent, "published": True, "queue_id": q.queue_id, "queue_status": q.status}


class QaDecision(BaseModel):
    answer: str | None = None            # 데스크가 고친 답 (없으면 AI 초안 그대로)


@router.get("/questions", summary="시청자 질문 목록 (AI 답변 초안·근거)")
def questions(status: str = "NEW,READY", db: Session = Depends(get_db), _: User = Depends(desk_only)):
    rows = (db.query(ViewerQuestion).filter(ViewerQuestion.status.in_(status.split(",")))
            .order_by(ViewerQuestion.q_id.desc()).limit(50).all())
    return [{"q_id": q.q_id, "nickname": q.nickname, "question": q.question, "answer": q.answer, "grounded": q.grounded,
             "sources": q.sources or [], "status": q.status, "ai_model": q.ai_model,
             "created_at": q.created_at.strftime("%H:%M:%S")} for q in rows]


@router.post("/questions/{q_id}/approve", summary="시청자 질문 방송 승인")
def approve_question(q_id: int, body: QaDecision = QaDecision(), db: Session = Depends(get_db), _: User = Depends(desk_only)):
    q = db.get(ViewerQuestion, q_id)
    if not q or q.status not in ("READY", "NEW"):
        raise HTTPException(409, "이미 처리됐거나 답변을 만드는 중입니다")
    if body.answer and body.answer.strip():
        q.answer = body.answer.strip()[:600]
    if not q.answer:
        raise HTTPException(409, "답변 초안이 아직 없습니다")
    q.status = "APPROVED"
    db.commit()
    from ..tasks import spawn
    from ..workers import qa_worker
    spawn(qa_worker.make_audio(q_id))
    broker.publish("onair", "qa.approved", {"q_id": q_id})
    return {"q_id": q_id, "status": q.status}


@router.post("/questions/{q_id}/reject", summary="시청자 질문 반려")
def reject_question(q_id: int, db: Session = Depends(get_db), _: User = Depends(desk_only)):
    q = db.get(ViewerQuestion, q_id)
    if not q or q.status in ("AIRED",):
        raise HTTPException(409, "이미 방송된 질문입니다")
    q.status = "REJECTED"
    db.commit()
    return {"q_id": q_id, "status": q.status}


@router.post("/articles/{article_id}/reject", summary="API-05-03 반려")
def reject(article_id: int, body: Decision, db: Session = Depends(get_db), desk: User = Depends(desk_only)):
    a = services.reject(db, article_id, desk, body.comment)
    return {"article_id": a.article_id, "status": a.status}
