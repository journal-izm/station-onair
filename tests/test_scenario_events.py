"""선관위 시나리오를 처음부터 끝까지 흘려 이벤트가 방송 흐름에 맞게 나오는지 확인 (FastAPI·DB 불필요).
tests/fixtures/hanbit_2026.csv 는 nec-server/scenario 의 사본입니다."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.logic import results  # noqa: E402

ELECTORS = {"STAR": 82000, "DEEP": 76000, "DUNE": 64000, "NEBULA": 71000, "ORBIT": 58000}


def replay():
    snap, prev, emitted, out = {}, results.summarize({}, ELECTORS, [1, 2, 3]), set(), []
    with open(ROOT / "tests" / "fixtures" / "hanbit_2026.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            snap[r["region_code"]] = {"counted_rate": float(r["counted_rate"]), "counted_votes": int(r["counted_votes"]),
                                      "votes": {1: int(r["v1"]), 2: int(r["v2"]), 3: int(r["v3"])}}
            cur = results.summarize(snap, ELECTORS, [1, 2, 3])
            for e in results.detect(prev, cur, emitted):
                out.append((float(r["t_sec"]), e))
            prev = cur
    return out, prev


def test_full_scenario_events():
    ev, final = replay()
    kinds = [e["event_type"] for _, e in ev]
    # 전체 개표율 구간 6개, 구별 50·100% 10개
    assert sum(1 for _, e in ev if e["event_type"] == "RATE_MILESTONE" and e["region_code"] == "ALL") == 6
    assert sum(1 for _, e in ev if e["event_type"] == "RATE_MILESTONE" and e["region_code"] != "ALL") == 10
    # 전체 1위 변동은 류해온 → 윤별하
    lead_all = [e for _, e in ev if e["event_type"] == "LEAD_CHANGE" and e["region_code"] == "ALL"]
    assert lead_all and lead_all[-1]["candidate_id"] == 1
    # 당선 단계는 유력 → 확실 → 확정 순서, 각 한 번, 모두 윤별하
    wins = [(t, e["event_type"], e["candidate_id"]) for t, e in ev if e["event_type"] in results.WIN_LEVELS]
    assert [w[1] for w in wins] == ["WIN_LIKELY", "WIN_SURE", "ELECTED"]
    assert all(w[2] == 1 for w in wins)
    assert 500 <= wins[-1][0] <= 620                       # LIVE 11분 안, 9~10분 무렵
    # 기사 수 추정 (01 기획서: 약 21~23건) — 너무 많으면 기자 3명이 감당 못함
    assert 15 <= len(kinds) <= 40
    assert final["ALL"].counted_rate == 100
