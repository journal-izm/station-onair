"""방송 엔진(logic.onair)과 DB(cue_sheet · onair_queue · media_asset · onair_state)를 잇는 곳."""
from __future__ import annotations

import threading
import time
from datetime import datetime

from . import config
from .db import SessionLocal
from .logic import rules
from .logic.onair import Broadcast
from .models import Article, AvatarVideo, Candidate, CueSheet, MediaAsset, OnairQueue, OnairState, TtsAudio
from .sse import broker

_lock = threading.Lock()
_engine: Broadcast | None = None


def _cues(db) -> list[dict]:
    return [{"cue_id": c.cue_id, "order_no": c.order_no, "segment_type": c.segment_type, "title": c.title,
             "duration_sec": c.duration_sec, "candidate_id": c.candidate_id}
            for c in db.query(CueSheet).order_by(CueSheet.order_no)]


def engine() -> Broadcast:
    global _engine
    if _engine is None:
        with SessionLocal() as db:
            _engine = Broadcast(_cues(db))
    return _engine


def reload_cues():
    global _engine
    _engine = None
    return engine()


def media_for(cue: dict, candidate_id: int | None) -> dict | None:
    """구간에 맞는 영상. 파일이 실제로 있어야 함 (없으면 SLATE로 제목만)."""
    mtype = {"ANCHOR": "OPENING"}.get(cue["segment_type"], cue["segment_type"])
    with SessionLocal() as db:
        q = db.query(MediaAsset).filter_by(media_type=mtype)
        if mtype in ("INTRO", "INTERVIEW", "PROFILE"):
            q = q.filter_by(candidate_id=candidate_id)
        m = q.first()
        if not m:
            return None
        if not (config.APP_DIR / m.file_path.lstrip("/")).exists():
            return None
        return {"file_path": m.file_path, "duration_sec": m.duration_sec}


def pop_item() -> dict | None:
    """대기열에서 다음 기사 (BR-07 순서). PLAYING으로 바꾸고 송출 정보를 돌려줌."""
    with SessionLocal() as db:
        waiting = db.query(OnairQueue).filter_by(status="WAITING").all()
        if not waiting:
            return None
        items = [{"queue_id": w.queue_id, "priority": w.priority, "approved_at": w.queued_at, "row": w} for w in waiting]
        q = sorted(items, key=rules.queue_sort_key)[0]["row"]
        a = db.get(Article, q.article_id)
        q.status, q.played_at = "PLAYING", datetime.now()
        st = db.get(OnairState, 1)
        if st:
            st.current_queue_id = q.queue_id
        db.commit()
        out = {"queue_id": q.queue_id, "article_id": a.article_id, "title": a.title, "script": a.anchor_script,
               "region_code": q.region_code, "event_type": q.event_type, "candidate_id": _event_candidate(db, a)}
        av = db.get(AvatarVideo, q.avatar_id) if q.avatar_id else None
        tts = db.get(TtsAudio, q.tts_id) if q.tts_id else None
        if av and av.status == "READY":
            out.update(media="AVATAR", src=av.file_path, audio=None, duration_sec=av.duration_sec or rules.expected_seconds(a.anchor_script))
        elif tts:
            out.update(media="TTS", audio=tts.file_path, duration_sec=tts.duration_sec)
        else:   # 키 없음 → 브라우저 음성
            out.update(media="SPEECH", audio=None, duration_sec=round(rules.expected_seconds(a.anchor_script), 1))
        return out


def _event_candidate(db, a: Article) -> int | None:
    from .models import CountEvent
    ev = db.get(CountEvent, a.event_id)
    return ev.candidate_id if ev else None


def _persist(eng: Broadcast):
    with SessionLocal() as db:
        st = db.get(OnairState, 1) or OnairState(id=1)
        st.status = eng.status
        st.current_cue_id = eng.cue["cue_id"] if eng.cue else None
        st.started_at = datetime.fromtimestamp(eng.started_at) if eng.started_at else None
        for i, c in enumerate(eng.cues):
            row = db.get(CueSheet, c["cue_id"])
            if row:
                row.status = "DONE" if i < eng.idx else ("ON_AIR" if i == eng.idx and eng.status != "STANDBY" else "READY")
        db.merge(st)
        db.commit()


def next_item() -> dict:
    with _lock:
        eng = engine()
        before = eng.cue["cue_id"] if eng.cue else None
        n = eng.next(time.time(), pop_item, media_for)
        after = eng.cue["cue_id"] if eng.cue else None
        _persist(eng)
    if before != after:
        broker.publish("onair", "cue.changed", {"cue_id": after, "order_no": n.get("order_no")})
    if n.get("kind") == "END":
        broker.publish("onair", "onair.control", {"action": "end"})
    return n


def item_done(queue_id: int, result: str = "DONE") -> dict:
    with SessionLocal() as db:
        q = db.get(OnairQueue, queue_id)
        if not q:
            return {"queue_id": queue_id, "status": "NOT_FOUND"}
        q.status = "DONE" if result == "DONE" else "SKIPPED"
        a = db.get(Article, q.article_id)
        cand = _event_candidate(db, a)
        db.commit()
        status = q.status
    with _lock:
        if result == "DONE":
            engine().item_played(q.event_type, cand)
    return {"queue_id": queue_id, "status": status}


def control(action: str) -> dict:
    with _lock:
        eng = engine()
        now = time.time()
        if action == "start":
            if eng.status in ("STANDBY", "ENDED"):
                eng = reload_cues()
            eng.start(now)
        elif action == "pause":
            eng.pause(now)
        elif action == "resume":
            eng.resume(now)
        elif action == "skip":
            eng.skip(now)
        elif action == "reset":
            eng = reload_cues()
        _persist(eng)
        snap = eng.snapshot(now)
    broker.publish("onair", "onair.control", {"action": action, **snap})
    return snap


def status() -> dict:
    with _lock:
        snap = engine().snapshot(time.time())
    with SessionLocal() as db:
        counts = {}
        for s, in db.query(OnairQueue.status):
            counts[s] = counts.get(s, 0) + 1
        winner = db.get(Candidate, snap["winner_id"]) if snap["winner_id"] else None
    return {**snap, "queue": counts, "winner_name": winner.name if winner else None}
