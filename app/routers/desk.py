"""영역 05 데스크 승인·출고 — API-05-01 ~ 03."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..models import Article, Region, User
from ..security import desk_only

router = APIRouter(prefix="/api/desk", tags=["05 데스크 승인·출고"])


class Decision(BaseModel):
    comment: str = ""


@router.get("/articles", summary="API-05-01 승인 대기 목록")
def waiting(status: str = "SUBMITTED", db: Session = Depends(get_db), _: User = Depends(desk_only)):
    users = {u.user_id: u.name for u in db.query(User)}
    names = {r.region_code: r.name for r in db.query(Region)}
    q = db.query(Article).filter(Article.status.in_(status.split(",")))
    q = q.order_by(Article.submitted_at.asc()) if status == "SUBMITTED" else q.order_by(Article.article_id.desc())
    now = datetime.now()
    return [{"article_id": a.article_id, "reporter": users.get(a.reporter_id), "title": a.title, "status": a.status,
             "event_type": a.event_type, "region": a.region_code, "region_name": names.get(a.region_code),
             "submitted_at": a.submitted_at.strftime("%H:%M:%S") if a.submitted_at else None,
             "approved_at": a.approved_at.strftime("%H:%M:%S") if a.approved_at else None,
             "waiting_sec": int((now - a.submitted_at).total_seconds()) if a.submitted_at and a.status == "SUBMITTED" else None}
            for a in q.limit(100)]


@router.post("/articles/{article_id}/approve", summary="API-05-02 승인(출고)")
def approve(article_id: int, body: Decision = Decision(), db: Session = Depends(get_db), desk: User = Depends(desk_only)):
    a, q = services.approve(db, article_id, desk, body.comment)
    return {"article_id": a.article_id, "status": a.status, "published": True, "queue_id": q.queue_id, "queue_status": q.status}


@router.post("/articles/{article_id}/reject", summary="API-05-03 반려")
def reject(article_id: int, body: Decision, db: Session = Depends(get_db), desk: User = Depends(desk_only)):
    a = services.reject(db, article_id, desk, body.comment)
    return {"article_id": a.article_id, "status": a.status}
