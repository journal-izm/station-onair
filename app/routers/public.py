"""영역 06 실시간 개표 웹 — API-06-01 ~ 04 (로그인 없이 공개, REQ-06-04)."""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Article, Candidate, Region, ResultLatest, ViewerQuestion
from ..sse import broker

router = APIRouter(prefix="/api/public", tags=["06 실시간 개표 웹 (공개)"])


def _region_block(db: Session, code: str, cands: dict, names: dict) -> dict:
    rows = db.query(ResultLatest).filter_by(region_code=code).order_by(ResultLatest.rank).all()
    leader = rows[0] if rows and rows[0].votes > 0 else None
    return {"code": code, "name": names.get(code, code),
            "counted_rate": rows[0].counted_rate if rows else 0.0,
            "leader": leader.candidate_id if leader else None,
            "leader_color": cands[leader.candidate_id].color if leader else None,
            "updated_at": rows[0].updated_at.strftime("%H:%M:%S") if rows else None,
            "candidates": [{"id": r.candidate_id, "name": cands[r.candidate_id].name, "party": cands[r.candidate_id].party,
                            "color": cands[r.candidate_id].color, "votes": r.votes, "rate": r.vote_rate, "rank": r.rank,
                            "winner_flag": r.winner_flag} for r in rows]}


@router.get("/results", summary="API-06-01 전체 개표 현황")
def results(db: Session = Depends(get_db)):
    cands = {c.candidate_id: c for c in db.query(Candidate)}
    names = {r.region_code: r.name for r in db.query(Region)}
    total = _region_block(db, "ALL", cands, names)
    if not total["candidates"]:      # 아직 개표 전 — 후보만
        total["candidates"] = [{"id": c.candidate_id, "name": c.name, "party": c.party, "color": c.color, "votes": 0,
                                "rate": 0.0, "rank": c.ballot_no, "winner_flag": None}
                               for c in sorted(cands.values(), key=lambda x: x.ballot_no)]
    regions = [_region_block(db, r.region_code, cands, names)
               for r in db.query(Region).filter(Region.region_code != "ALL").order_by(Region.sort_order)]
    return {"counted_rate": total["counted_rate"], "updated_at": total["updated_at"], "candidates": total["candidates"],
            "regions": regions}


@router.get("/results/{region_code}", summary="API-06-02 지역별 결과")
def region(region_code: str, db: Session = Depends(get_db)):
    if not db.get(Region, region_code):
        raise HTTPException(404, "없는 지역 코드입니다")
    cands = {c.candidate_id: c for c in db.query(Candidate)}
    names = {r.region_code: r.name for r in db.query(Region)}
    b = _region_block(db, region_code, cands, names)
    reg = db.get(Region, region_code)
    return {"region": b["name"], "code": region_code, "electors": reg.electors, **b}


@router.get("/articles", summary="API-06-03 출고 기사 목록")
def articles(region: str | None = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(Article).filter(Article.status == "APPROVED")          # BR-01: 승인된 기사만
    if region:
        q = q.filter(Article.region_code == region)
    names = {r.region_code: r.name for r in db.query(Region)}
    return [{"article_id": a.article_id, "title": a.title, "body": a.body, "region": a.region_code,
             "region_name": names.get(a.region_code), "event_type": a.event_type, "urgent": bool(a.urgent),
             "approved_at": a.approved_at.strftime("%H:%M:%S") if a.approved_at else None}
            for a in q.order_by(Article.urgent.desc(), Article.approved_at.desc()).limit(min(limit, 100))]   # 긴급 기사는 맨 위


class Ask(BaseModel):
    question: str = Field(min_length=5, max_length=200)
    nickname: str = Field(default="시청자", max_length=20)


_last_ask: dict[str, float] = {}


@router.post("/questions", summary="시청자 질문 보내기 (QR)")
def ask(body: Ask, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    if time.time() - _last_ask.get(ip, 0) < 20:                      # 같은 휴대폰에서 20초에 한 번
        raise HTTPException(429, "잠시 뒤에 다시 보내 주세요")
    _last_ask[ip] = time.time()
    q = ViewerQuestion(question=body.question.strip(), nickname=(body.nickname or "시청자").strip()[:20] or "시청자")
    db.add(q)
    db.commit()
    from ..workers import qa_worker
    qa_worker.schedule(q.q_id)
    broker.publish("newsroom", "qa.new", {"q_id": q.q_id})
    return {"q_id": q.q_id, "status": q.status, "message": "질문이 접수됐습니다. 데스크가 고른 질문은 방송에서 앵커가 답합니다."}


@router.get("/stream", summary="API-06-04 실시간 알림 (SSE)")
def stream(request: Request):
    return broker.response("public", request)
