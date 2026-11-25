"""영역 03 개표 수신 — API-03-01 · 02 (데스크)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CountEvent, Region, SyncLog
from ..security import desk_only
from ..workers import article_gen, sync_worker

router = APIRouter(prefix="/api/sync", tags=["03 개표 수신"], dependencies=[Depends(desk_only)])


@router.get("/status", summary="API-03-01 수신 상태")
def status(db: Session = Depends(get_db)):
    st = sync_worker.state
    last = db.query(SyncLog).order_by(SyncLog.log_id.desc()).first()
    _, last_seq = sync_worker.snapshot(db)
    names = {r.region_code: r.name for r in db.query(Region)}
    events = db.query(CountEvent).order_by(CountEvent.event_id.desc()).limit(15).all()
    logs = db.query(SyncLog).order_by(SyncLog.log_id.desc()).limit(10).all()
    return {
        "state": "OK" if st.fail_count == 0 else "FAIL",
        "last_seq": last_seq,
        "last_at": st.last_ok_at.strftime("%H:%M:%S") if st.last_ok_at else None,
        "fail_count": st.fail_count, "last_error": st.last_error,
        "last_request_at": last.requested_at.strftime("%H:%M:%S") if last else None,
        "ai": article_gen.stats,
        "recent_events": [{"event_id": e.event_id, "type": e.event_type, "region": e.region_code,
                           "region_name": names.get(e.region_code), "seq": e.seq,
                           "at": e.detected_at.strftime("%H:%M:%S"), "rate": e.payload.get("counted_rate")} for e in events],
        "logs": [{"at": l.requested_at.strftime("%H:%M:%S"), "since": l.since_seq, "last": l.last_seq,
                  "rows": l.row_count, "status": l.status, "error": l.error_msg} for l in logs],
    }


@router.post("/run", summary="API-03-02 즉시 수신")
async def run_now():
    return await sync_worker.run_once()
