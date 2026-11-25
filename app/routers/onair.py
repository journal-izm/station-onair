"""영역 07 개표 방송 송출 — API-07-01 ~ 05 (데스크·송출 PC)."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import onair_service
from ..db import get_db
from ..models import Article, AvatarVideo, CueSheet, MediaAsset, OnairQueue, Region
from ..security import desk_only
from ..sse import broker

router = APIRouter(prefix="/api/onair", tags=["07 방송 송출"], dependencies=[Depends(desk_only)])


class Done(BaseModel):
    result: Literal["DONE", "ERROR"] = "DONE"


class Control(BaseModel):
    action: Literal["start", "pause", "resume", "skip", "reset"]


@router.get("/cuesheet", summary="API-07-01 큐시트 조회")
def cuesheet(db: Session = Depends(get_db)):
    from .. import config
    media = {m.media_id: m for m in db.query(MediaAsset)}
    out = []
    for c in db.query(CueSheet).order_by(CueSheet.order_no):
        files = [m for m in media.values() if m.media_type == {"ANCHOR": "OPENING"}.get(c.segment_type, c.segment_type)
                 and (c.candidate_id is None or m.candidate_id == c.candidate_id)]
        ready = [m.file_path for m in files if (config.APP_DIR / m.file_path.lstrip("/")).exists()]
        out.append({"cue_id": c.cue_id, "order_no": c.order_no, "segment_type": c.segment_type, "title": c.title,
                    "planned_start_sec": c.planned_start_sec, "duration_sec": c.duration_sec, "trigger_type": c.trigger_type,
                    "status": c.status, "media_needed": [m.file_path for m in files], "media_ready": ready,
                    "media_missing": [m.file_path for m in files if m.file_path not in ready]})
    return out


@router.get("/next", summary="API-07-02 다음 송출 항목")
def next_item():
    return onair_service.next_item()


@router.post("/queue/{queue_id}/done", summary="API-07-03 송출 완료 보고")
def done(queue_id: int, body: Done = Done()):
    return onair_service.item_done(queue_id, body.result)


@router.post("/control", summary="API-07-04 송출 제어")
def control(body: Control):
    return onair_service.control(body.action)


@router.get("/status", summary="송출 상태 (큐시트 화면용)")
def status(db: Session = Depends(get_db)):
    names = {r.region_code: r.name for r in db.query(Region)}
    q = (db.query(OnairQueue, Article).join(Article, Article.article_id == OnairQueue.article_id)
         .order_by(OnairQueue.queue_id.desc()).limit(20).all())
    return {**onair_service.status(),
            "queue_items": [{"queue_id": o.queue_id, "title": a.title, "status": o.status, "priority": o.priority,
                             "region_name": names.get(o.region_code), "media": _media_label(db, o)}
                            for o, a in q]}


def _media_label(db: Session, o: OnairQueue) -> str:
    av = db.get(AvatarVideo, o.avatar_id) if o.avatar_id else None
    if av and av.status == "READY":
        return "AVATAR"
    if o.tts_id:
        return "TTS"
    return "준비 중" if o.status == "PREPARING" else "브라우저 음성"


@router.get("/stream", summary="API-07-05 송출 상태 알림 (SSE)")
def stream(request: Request):
    return broker.response("onair", request)
