"""기사 상태 변화와 방송 대기열 (FN-04-04 · 05, FN-05-02 · 03, BR-01 · 02 · 03 · 04 · 06)."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from .db import SessionLocal
from .logic import rules
from .models import Article, ArticleReview, OnairQueue, User
from .sse import broker


def get_article(db: Session, article_id: int) -> Article:
    a = db.get(Article, article_id)
    if not a:
        raise HTTPException(404, "기사를 찾을 수 없습니다")
    return a


def check_owner(a: Article, user: User):
    if a.reporter_id != user.user_id:                         # BR-02
        raise HTTPException(403, "내게 배정된 기사만 고칠 수 있습니다")


def edit(db: Session, a: Article, user: User, title: str, body: str, script: str) -> Article:
    check_owner(a, user)
    if not rules.can_edit(a.status):                          # BR-03
        raise HTTPException(409, f"{a.status} 상태에서는 고칠 수 없습니다")
    a.title, a.body, a.anchor_script = title[:100], body, script
    db.commit()
    return a


def submit(db: Session, a: Article, user: User) -> Article:
    check_owner(a, user)
    if not rules.can_submit(a.status):
        raise HTTPException(409, f"{a.status} 상태에서는 송고할 수 없습니다")
    a.status, a.submitted_at = "SUBMITTED", datetime.now()
    db.commit()
    broker.publish("newsroom", "article.submitted", {"article_id": a.article_id})
    return a


def _decide(db: Session, article_id: int, desk: User, to: str) -> Article:
    """BR-04: SUBMITTED일 때만 바꾸기 — 두 데스크가 동시에 눌러도 한 명만 성공."""
    values = {"status": to, "desk_id": desk.user_id}
    if to == "APPROVED":
        values["approved_at"] = datetime.now()
    res = db.execute(update(Article).where(Article.article_id == article_id, Article.status == "SUBMITTED").values(**values))
    if res.rowcount == 0:
        db.rollback()
        a = db.get(Article, article_id)
        if not a:
            raise HTTPException(404, "기사를 찾을 수 없습니다")
        raise HTTPException(409, "이미 처리된 기사입니다")
    db.add(ArticleReview(article_id=article_id, desk_id=desk.user_id,
                         action="APPROVE" if to == "APPROVED" else "REJECT"))
    db.flush()
    db.expire_all()                      # 방금 바꾼 상태를 다시 읽도록
    return db.get(Article, article_id)


def approve(db: Session, article_id: int, desk: User, comment: str = "", urgent: bool = False) -> tuple[Article, OnairQueue]:
    a = _decide(db, article_id, desk, "APPROVED")
    a = db.get(Article, article_id)
    a.urgent = bool(urgent)
    if comment:
        db.query(ArticleReview).filter_by(article_id=article_id).order_by(ArticleReview.review_id.desc()).first().comment = comment[:300]
    q = enqueue(db, a)
    db.commit()
    broker.publish("public", "article.published", {"article_id": a.article_id, "region": a.region_code, "urgent": a.urgent})
    broker.publish("newsroom", "article.approved", {"article_id": a.article_id})
    broker.publish("onair", "queue.changed", {"queue_id": q.queue_id, "urgent": a.urgent})
    from .workers import tts_worker
    tts_worker.schedule(q.queue_id)
    return a, q


def reject(db: Session, article_id: int, desk: User, comment: str) -> Article:
    if not comment.strip():
        raise HTTPException(422, "반려 사유를 적어 주세요")
    a = _decide(db, article_id, desk, "REJECTED")
    db.query(ArticleReview).filter_by(article_id=article_id).order_by(ArticleReview.review_id.desc()).first().comment = comment[:300]
    db.commit()
    broker.publish("newsroom", "article.rejected", {"article_id": a.article_id, "reporter_id": a.reporter_id})
    return a


def enqueue(db: Session, a: Article) -> OnairQueue:
    """승인 기사 → 방송 대기열 (PREPARING). BR-06 옛 기사 건너뛰기."""
    q = OnairQueue(article_id=a.article_id, region_code=a.region_code, priority=rules.priority(a.event_type, a.urgent),
                   status="PREPARING", event_type=a.event_type, queued_at=datetime.now())
    db.add(q)
    db.flush()
    waiting = [{"queue_id": w.queue_id, "region_code": w.region_code, "event_type": w.event_type, "status": w.status,
                "approved_at": w.queued_at} for w in db.query(OnairQueue).filter(OnairQueue.status.in_(("PREPARING", "WAITING")),
                                                       OnairQueue.priority != rules.URGENT_PRIORITY)]   # 긴급·대기(HOLD)는 자동 건너뛰기 안 함
    new = {"queue_id": q.queue_id, "region_code": q.region_code, "event_type": q.event_type, "approved_at": q.queued_at}
    for qid in rules.stale_items(new, waiting):
        db.get(OnairQueue, qid).status = "SKIPPED"
    return q


async def demo_auto_publish(article_id: int):
    """시연 모드 전용: 담당 기자 송고 → 데스크1 승인을 자동으로 (발표 녹화·클라우드 시연용)."""
    with SessionLocal() as db:
        a = db.get(Article, article_id)
        reporter = db.get(User, a.reporter_id)
        desk = db.query(User).filter_by(role="DESK").order_by(User.user_id).first()
        submit(db, a, reporter)
        approve(db, article_id, desk, "시연 모드 자동 승인")
