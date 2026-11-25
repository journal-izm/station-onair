"""FN-03-01 · 02 · 03 — 5초마다 선관위 변경분 받기 → 최신 결과 갱신 → 이벤트 감지 → 기사 생성 요청."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, nec_client
from ..db import SessionLocal
from ..logic import results as R
from ..models import Candidate, CountEvent, Region, ResultLatest, SyncLog
from ..sse import broker

log = logging.getLogger("sync")
FLAG = {"WIN_LIKELY": "LIKELY", "WIN_SURE": "SURE", "ELECTED": "ELECTED"}


class SyncState:
    def __init__(self):
        self.fail_count = 0
        self.last_ok_at: datetime | None = None
        self.last_error: str | None = None
        self.running = False
        self.election_loaded = False


state = SyncState()
_lock = asyncio.Lock()


# ── DB → 계산용 자료 ──
def meta(db: Session):
    regions = db.query(Region).filter(Region.region_code != R.ALL).order_by(Region.sort_order).all()
    cands = db.query(Candidate).order_by(Candidate.ballot_no).all()
    return {r.region_code: r.electors for r in regions}, [c.candidate_id for c in cands], {c.candidate_id: c.name for c in cands}


def snapshot(db: Session) -> tuple[dict, int]:
    snap, last_seq = {}, 0
    for row in db.query(ResultLatest).filter(ResultLatest.region_code != R.ALL).all():
        s = snap.setdefault(row.region_code, {"counted_rate": row.counted_rate, "counted_votes": row.counted_votes, "votes": {}})
        s["votes"][row.candidate_id] = row.votes
        last_seq = max(last_seq, row.updated_seq)
    return snap, last_seq


def emitted_keys(db: Session) -> set:
    keys = set()
    for (k,) in db.query(CountEvent.event_key).filter(CountEvent.event_key.isnot(None)).all():
        keys.add(k)
        if k.startswith("WIN:"):       # 높은 단계가 있으면 낮은 단계도 지난 것으로
            lvl = k.split(":")[1]
            for x in R.WIN_LEVELS[: R.WIN_LEVELS.index(lvl)]:
                keys.add(f"WIN:{x}")
        if k.startswith("RATE:"):
            _, code, m = k.split(":")
            for x in (R.ALL_MILESTONES if code == R.ALL else R.REGION_MILESTONES):
                if x < int(m):
                    keys.add(f"RATE:{code}:{x}")
    return keys


async def ensure_election(db: Session) -> None:
    """서버가 켜진 뒤 처음 한 번: 선관위 기본정보(API-02-01)로 후보·지역 복제 (TBL-03-01 · 02)."""
    if state.election_loaded:
        return
    info = await nec_client.election_info()
    for c in info["candidates"]:
        db.merge(Candidate(candidate_id=c["id"], ballot_no=c["ballot_no"], name=c["name"], party=c.get("party"), color=c["color"]))
    db.merge(Region(region_code=R.ALL, name="전체", electors=info["election"]["total_electors"], sort_order=0))
    for r in info["regions"]:
        db.merge(Region(region_code=r["code"], name=r["name"], electors=r["electors"], sort_order=r.get("sort_order", 0)))
    db.commit()
    state.election_loaded = True


def save_results(db: Session, summ: dict, seq: int) -> None:
    lvl = R.win_level(summ[R.ALL])
    ts = datetime.now()
    for code, s in summ.items():
        for cid in s.votes:
            row = db.get(ResultLatest, (code, cid)) or ResultLatest(region_code=code, candidate_id=cid)
            row.votes, row.vote_rate, row.rank = s.votes[cid], s.vote_rate(cid), s.rank(cid)
            row.counted_rate, row.counted_votes = s.counted_rate, s.counted_votes
            row.winner_flag = FLAG.get(lvl) if (code == R.ALL and cid == s.leader and lvl) else None
            row.updated_seq, row.updated_at = seq, ts
            db.merge(row)


def save_events(db: Session, events: list[dict], seq: int) -> list[int]:
    ids = []
    for e in events:
        ev = CountEvent(event_type=e["event_type"], region_code=e["region_code"], candidate_id=e["candidate_id"],
                        payload=e["payload"], seq=seq, event_key=e["key"])
        try:
            with db.begin_nested():         # 이 한 건만 되돌릴 수 있게 (savepoint)
                db.add(ev)
                db.flush()
            ids.append(ev.event_id)
        except IntegrityError:          # 같은 열쇠가 이미 있으면 건너뜀 (TC-DB-04)
            pass
    return ids


def apply_rows(db: Session, rows: list[dict]) -> tuple[list[int], int]:
    """변경분을 반영하고 새 이벤트 번호들과 마지막 seq를 돌려줌. 순수 계산은 logic.results가 담당."""
    electors, cands, names = meta(db)
    snap, last_seq = snapshot(db)
    prev = R.summarize(snap, electors, cands)
    emitted = emitted_keys(db)
    new_ids = []
    for row in sorted(rows, key=lambda r: r["seq"]):      # 한 줄씩 반영해 중간 사건도 놓치지 않음
        if row["seq"] <= last_seq:
            continue
        snap[row["code"]] = {"counted_rate": row["counted_rate"], "counted_votes": row.get("counted_votes", 0),
                             "votes": {int(k): v for k, v in row["votes"].items()}}
        cur = R.summarize(snap, electors, cands)
        events = R.detect(prev, cur, emitted, names)
        new_ids += save_events(db, events, row["seq"])
        prev, last_seq = cur, row["seq"]
    if rows:
        save_results(db, prev, last_seq)
    db.commit()
    return new_ids, last_seq


async def run_once() -> dict:
    """API-03-02 즉시 수신과 5초 루프가 같이 씀."""
    async with _lock:
        with SessionLocal() as db:
            _, since = snapshot(db)
            logrow = SyncLog(since_seq=since, status="OK")
            try:
                await ensure_election(db)
                received, new_ids = 0, []
                while True:
                    data = await nec_client.results(since)
                    rows = data.get("regions", [])
                    ids, since2 = apply_rows(db, rows)
                    received += len(rows)
                    new_ids += ids
                    since = max(since, since2)
                    if not data.get("has_more") or not rows:
                        break
                logrow.last_seq, logrow.row_count = since, received
                state.fail_count, state.last_ok_at, state.last_error = 0, datetime.now(), None
            except nec_client.NecError as e:
                logrow.status, logrow.error_msg = "FAIL", str(e)[:200]
                state.fail_count += 1
                state.last_error = str(e)
                received, new_ids = 0, []
            db.add(logrow)
            db.commit()
        if received:
            broker.publish("public", "results.updated", {"last_seq": since})
            broker.publish("onair", "results.updated", {"last_seq": since})
        if new_ids:
            from . import article_gen
            for eid in new_ids:
                article_gen.schedule(eid)
            broker.publish("newsroom", "events.detected", {"count": len(new_ids)})
        return {"received": received, "last_seq": since, "new_events": len(new_ids), "ok": logrow.status == "OK"}


async def loop_forever():
    state.running = True
    while True:
        try:
            await run_once()
        except Exception:
            log.exception("수신 루프 오류")       # 루프는 멈추지 않음
            state.fail_count += 1
        # 실패하면 조금씩 늦춰 다시 시도 (최대 30초) — REQ-03-03
        await asyncio.sleep(config.SYNC_INTERVAL_SEC if state.fail_count == 0 else min(30, config.SYNC_INTERVAL_SEC * (1 + state.fail_count)))
