"""영역 04 기사 — API-04-01 ~ 05 (기자)."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..models import Article, ArticleReview, CandidateDoc, CountEvent, Region, User
from ..security import reporter_only, staff
from ..sse import broker

router = APIRouter(prefix="/api", tags=["04 기사 작성·송고"])


class Edit(BaseModel):
    title: str
    body: str
    anchor_script: str


def row(a: Article, names: dict | None = None) -> dict:
    return {"article_id": a.article_id, "title": a.title, "status": a.status, "event_type": a.event_type,
            "urgent": bool(a.urgent), "region": a.region_code, "region_name": (names or {}).get(a.region_code),
            "created_at": a.created_at.strftime("%H:%M:%S"), "ai_model": a.ai_model,
            "submitted_at": a.submitted_at.strftime("%H:%M:%S") if a.submitted_at else None}


@router.get("/articles", summary="API-04-01 내 기사 목록")
def my_articles(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(reporter_only)):
    q = db.query(Article).filter_by(reporter_id=user.user_id)
    if status:
        q = q.filter(Article.status.in_(status.split(",")))
    names = {r.region_code: r.name for r in db.query(Region)}
    return [row(a, names) for a in q.order_by(Article.article_id.desc()).limit(100)]


@router.get("/articles/{article_id}", summary="API-04-02 기사 상세")
def detail(article_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    a = services.get_article(db, article_id)
    if user.role == "REPORTER":
        services.check_owner(a, user)
    ev = db.get(CountEvent, a.event_id)
    docs = db.query(CandidateDoc).filter(CandidateDoc.doc_id.in_(a.rag_sources or [])).all()
    reviews = db.query(ArticleReview).filter_by(article_id=a.article_id).order_by(ArticleReview.review_id).all()
    users = {u.user_id: u.name for u in db.query(User)}
    return {**row(a), "body": a.body, "anchor_script": a.anchor_script, "reporter": users.get(a.reporter_id),
            "event": {"type": ev.event_type, "region": ev.region_code, "seq": ev.seq, **ev.payload} if ev else None,
            "rag_sources": [{"doc_id": d.doc_id, "title": d.title, "source": d.source} for d in docs],
            "reviews": [{"action": r.action, "desk": users.get(r.desk_id), "comment": r.comment,
                         "at": r.created_at.strftime("%H:%M:%S")} for r in reviews]}


@router.put("/articles/{article_id}", summary="API-04-03 기사 수정(임시 저장)")
def edit(article_id: int, body: Edit, db: Session = Depends(get_db), user: User = Depends(reporter_only)):
    a = services.edit(db, services.get_article(db, article_id), user, body.title, body.body, body.anchor_script)
    return {"article_id": a.article_id, "status": a.status, "updated": True}


@router.post("/articles/{article_id}/submit", summary="API-04-04 송고")
def submit(article_id: int, db: Session = Depends(get_db), user: User = Depends(reporter_only)):
    a = services.submit(db, services.get_article(db, article_id), user)
    return {"article_id": a.article_id, "status": a.status, "submitted_at": a.submitted_at.strftime("%H:%M:%S")}


@router.get("/newsroom/stream", summary="API-04-05 뉴스룸 알림 (SSE)")
def newsroom_stream(request: Request, user: User = Depends(staff)):
    return broker.response("newsroom", request)
