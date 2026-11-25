"""방송 엔진(logic.onair)과 DB(cue_sheet · onair_queue · media_asset · onair_state)를 잇는 곳."""
from __future__ import annotations

import logging
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
        from .models import CountEvent, Region
        ev = db.get(CountEvent, a.event_id)
        reg = db.get(Region, q.region_code)
        out = {"queue_id": q.queue_id, "article_id": a.article_id, "title": a.title, "script": a.anchor_script,
               "urgent": q.priority == rules.URGENT_PRIORITY, "intro_audio": urgent_intro_url(),
               "region_code": q.region_code, "region_name": reg.name if reg else q.region_code,
               "event_type": q.event_type, "candidate_id": ev.candidate_id if ev else None,
               # 기사를 쓸 때의 개표 수치 — 송출 화면이 '기사 관련 차트'를 이 숫자로 그림 (기사와 화면 숫자가 같게)
               "event": {**(ev.payload if ev else {}), "seq": ev.seq if ev else None,
                         "detected_at": ev.detected_at.strftime("%H:%M:%S") if ev else None}}
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


# ── 긴급 속보 머리말 ("긴급 속보입니다.") — TTS로 한 번만 만들어 두고 긴급 기사마다 앞에 붙임
URGENT_INTRO_TEXT = "긴급 속보입니다."


def _intro_path():
    return config.TTS_DIR / f"urgent_intro_{config.STATION_CODE.lower()}.wav"


def urgent_intro_url() -> str | None:
    return f"/static/tts/{_intro_path().name}" if _intro_path().exists() else None


def make_urgent_intro():
    """서버 시작 때 스레드에서 부름. 키가 없거나 실패하면 송출 화면이 브라우저 음성으로 말함."""
    if not config.OPENAI_API_KEY or _intro_path().exists():
        return
    try:
        from .workers.tts_worker import synth
        config.TTS_DIR.mkdir(parents=True, exist_ok=True)
        synth(URGENT_INTRO_TEXT, _intro_path())
    except Exception as e:
        logging.getLogger("tts").warning("긴급 속보 머리말 음성 실패: %s", e)


# ── 큐시트 방송 대기열 버튼: 긴급 / 자동 / 대기 / 삭제 / 모두 삭제
QUEUE_MODES = ("URGENT", "AUTO", "HOLD", "DELETE", "DELETE_ALL")


def set_queue_mode(queue_id: int, mode: str) -> dict:
    with SessionLocal() as db:
        q = db.get(OnairQueue, queue_id)
        if not q:
            raise LookupError("대기열 항목을 찾을 수 없습니다")
        if q.status not in ("PREPARING", "WAITING", "HOLD") and not (mode == "DELETE_ALL" and q.status == "DELETED"):
            raise ValueError(f"이미 {q.status} 상태라 바꿀 수 없습니다")
        a = db.get(Article, q.article_id)
        ready = q.tts_id is not None or q.avatar_id is not None or not config.OPENAI_API_KEY
        release = ("WAITING" if ready else "PREPARING") if q.status == "HOLD" else q.status
        if mode == "URGENT":
            q.priority, q.queued_at, q.status = rules.URGENT_PRIORITY, datetime.now(), release   # 긴급끼리는 누른 순서
            a.urgent = True
        elif mode == "AUTO":
            q.priority, q.status = rules.priority(q.event_type), release
            a.urgent = False
        elif mode == "HOLD":
            q.status = "HOLD"
        elif mode == "DELETE":
            q.status = "DELETED"                        # 방송에서만 뺌, 웹 기사는 그대로
        elif mode == "DELETE_ALL":
            q.status = "DELETED"
            a.status = "WITHDRAWN"                      # 웹에서도 내림
        db.commit()
        out = {"queue_id": q.queue_id, "status": q.status, "urgent": q.priority == rules.URGENT_PRIORITY,
               "article_status": a.status}
        article_id = q.article_id
        need_prepare = mode in ("URGENT", "AUTO") and out["status"] == "PREPARING"
    if need_prepare:
        from .workers import tts_worker
        tts_worker.schedule(queue_id)
    broker.publish("onair", "queue.changed", {"queue_id": queue_id, "mode": mode, "urgent": out["urgent"]})
    if mode in ("URGENT", "AUTO", "DELETE_ALL"):
        broker.publish("public", "article.published", {"article_id": article_id})   # 웹 기사 목록 새로고침
    return out


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
