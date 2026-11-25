"""순수 로직 테스트 — FastAPI·DB 없이 돌아감. 1차 확인 테스트케이스 번호와 같은 이름."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.logic import onair, results, retrieve, rules, writer  # noqa: E402

ELECTORS = {"STAR": 82000, "DEEP": 76000, "DUNE": 64000, "NEBULA": 71000, "ORBIT": 58000}
CANDS = [1, 2, 3]
NAMES = {1: "윤별하", 2: "류해온", 3: "오로라"}
REGION_NAMES = {"ALL": "전체", "STAR": "별빛구", "DEEP": "심해구", "DUNE": "사막구", "NEBULA": "성운구", "ORBIT": "궤도구"}


def snap(rate, v1, v2, v3=0, code="STAR", ballots=50000):
    counted = round(ballots * rate / 100)
    return {code: {"counted_rate": rate, "counted_votes": counted, "votes": {1: v1, 2: v2, 3: v3}}}


def one_region(rate, v1, v2, v3=0):
    return results.summarize(snap(rate, v1, v2, v3), {"STAR": 82000}, CANDS)


# ── TC-FN-02 개표율·1위 변동 감지 ──
def test_tc_fn_02_milestone_and_lead_change():
    prev = one_region(28, 7000, 6500, 500)       # 1위 윤별하
    cur = one_region(31, 7300, 8000, 200)        # 1위 류해온
    emitted = set()
    ev = results.detect(prev, cur, emitted, NAMES)
    types = sorted((e["event_type"], e["region_code"]) for e in ev)
    assert ("RATE_MILESTONE", "ALL") in types and ("LEAD_CHANGE", "ALL") in types
    assert [e for e in ev if e["event_type"] == "RATE_MILESTONE" and e["region_code"] == "ALL"][0]["payload"]["milestone"] == 30
    # 같은 값을 다시 넣어도 새 이벤트 없음
    assert results.detect(cur, cur, emitted, NAMES) == []


def test_milestone_jump_reports_highest_only():
    emitted = set()
    ev = results.detect(one_region(5, 10, 5), one_region(55, 1000, 500), emitted, NAMES)
    ms = [e["payload"]["milestone"] for e in ev if e["event_type"] == "RATE_MILESTONE" and e["region_code"] == "ALL"]
    assert ms == [50] and {"RATE:ALL:10", "RATE:ALL:30", "RATE:ALL:50"} <= emitted


# ── TC-FN-03 당선 판정 ──
def test_tc_fn_03_win_levels():
    s = results.summarize({"STAR": {"counted_rate": 80, "counted_votes": 40000, "votes": {1: 21000, 2: 18000, 3: 1000}}},
                          {"STAR": 82000}, CANDS)["ALL"]
    # 전체 투표 50000 추정, 남은 10000, 격차 3000 → 30% 이상 → 당선 유력
    assert results.win_level(s) == "WIN_LIKELY"
    s2 = results.summarize({"STAR": {"counted_rate": 80, "counted_votes": 40000, "votes": {1: 25000, 2: 14000, 3: 1000}}},
                           {"STAR": 82000}, CANDS)["ALL"]
    assert results.win_level(s2) == "ELECTED"            # 격차 11000 > 남은 10000
    s3 = results.summarize({"STAR": {"counted_rate": 80, "counted_votes": 40000, "votes": {1: 22600, 2: 16400, 3: 1000}}},
                           {"STAR": 82000}, CANDS)["ALL"]
    assert results.win_level(s3) == "WIN_SURE"           # 격차 6200 > 남은 표의 60%
    s4 = results.summarize({"STAR": {"counted_rate": 100, "counted_votes": 50000, "votes": {1: 20000, 2: 19990, 3: 10}}},
                           {"STAR": 82000}, CANDS)["ALL"]
    assert results.win_level(s4) == "ELECTED"            # 개표 100%


def test_win_events_once_and_highest_only():
    emitted = set()
    before = one_region(40, 8000, 7900, 100)
    after = results.summarize({"STAR": {"counted_rate": 100, "counted_votes": 50000, "votes": {1: 26000, 2: 23000, 3: 1000}}},
                              {"STAR": 82000}, CANDS)
    ev = [e for e in results.detect(before, after, emitted, NAMES) if e["event_type"] in results.WIN_LEVELS]
    assert [e["event_type"] for e in ev] == ["ELECTED"]
    assert {"WIN:WIN_LIKELY", "WIN:WIN_SURE", "WIN:ELECTED"} <= emitted
    assert [e for e in results.detect(after, after, emitted, NAMES)] == []


def test_tc_db_03_summary_has_all_and_regions():
    s = results.summarize({}, ELECTORS, CANDS)
    assert set(s) == set(ELECTORS) | {"ALL"}
    assert sum(len(x.votes) for x in s.values()) == 18          # 구 5 × 3 + 전체 3 (result_latest 18행)


# ── TC-FN-04 기자 자동 배정 (BR-05) ──
def test_tc_fn_04_assign_round_robin_and_skip():
    ids, last, pending, got = [1, 2, 3], None, {}, []
    for _ in range(5):
        r = rules.next_reporter(ids, last, pending)
        got.append(r)
        last = r
    assert got == [1, 2, 3, 1, 2]
    assert rules.next_reporter(ids, 3, {1: 3, 2: 0, 3: 0}) == 2   # 기자1 미처리 3건 → 건너뜀
    assert rules.next_reporter(ids, 3, {1: 4, 2: 3, 3: 5}) == 2   # 모두 많으면 가장 적은 기자


# ── TC-FN-05 기사 상태 (BR-03) ──
def test_tc_fn_05_editable_states():
    assert rules.can_edit("DRAFT") and rules.can_edit("REJECTED")
    assert not rules.can_edit("SUBMITTED") and not rules.can_edit("APPROVED")
    assert rules.can_submit("REJECTED") and not rules.can_submit("SUBMITTED")


# ── TC-FN-07 대기열 순서와 건너뛰기 (BR-06·07) ──
def test_tc_fn_07_queue_order_and_stale():
    q = [{"queue_id": 1, "priority": 5, "approved_at": 1, "region_code": "STAR", "event_type": "RATE_MILESTONE", "status": "WAITING"},
         {"queue_id": 2, "priority": 3, "approved_at": 2, "region_code": "DEEP", "event_type": "LEAD_CHANGE", "status": "WAITING"},
         {"queue_id": 3, "priority": 1, "approved_at": 3, "region_code": "ALL", "event_type": "ELECTED", "status": "WAITING"}]
    assert [x["queue_id"] for x in sorted(q, key=rules.queue_sort_key)] == [3, 2, 1]
    new = {"queue_id": 4, "priority": 5, "approved_at": 4, "region_code": "STAR", "event_type": "RATE_MILESTONE", "status": "PREPARING"}
    assert rules.stale_items(new, q) == [1]
    assert rules.stale_items(q[2], q) == []          # 당선 기사는 건너뛰지 않음


# ── TC-FN-08 TTS 다시 만들기 기준 (BR-08) ──
def test_tc_fn_08_tts_length_check():
    script = "가" * 120                                 # 예상 20초
    assert rules.tts_ok(script, 18) and not rules.tts_ok(script, 10) and not rules.tts_ok(script, None)


# ── TC-FN-09 아바타 대기 한도 (BR-11) ──
def test_tc_fn_09_avatar_timeout():
    assert rules.is_avatar_target("ELECTED") and not rules.is_avatar_target("LEAD_CHANGE")
    assert rules.avatar_decision("REQUESTED", 10, 90) == "WAIT"
    assert rules.avatar_decision("REQUESTED", 90, 90) == "TTS"
    assert rules.avatar_decision("READY", 95, 90) == "AVATAR"
    assert rules.avatar_decision("FAILED", 1, 90) == "TTS"


# ── 틀 기사·AI 답 읽기 ──
def test_template_article_and_parse():
    ev = {"event_type": "LEAD_CHANGE", "region_code": "STAR",
          "payload": {"counted_rate": 51.3, "votes": {"2": 15210, "1": 14877, "3": 2100},
                      "vote_rates": {"2": 46.7, "1": 45.7, "3": 6.4}, "leader": 2, "leader_name": "류해온",
                      "prev_leader": 1, "prev_leader_name": "윤별하", "gap": 333, "remaining": 25000}}
    f = writer.facts(ev, REGION_NAMES, NAMES)
    a = writer.template_article(f)
    assert "별빛구" in a["title"] and "류해온" in a["body"]
    assert 90 <= len(a["anchor_script"]) <= 220
    assert writer.numbers_match(a, f)
    msgs = writer.build_messages(None, None, f, [{"doc_id": 1, "title": "류해온 이력", "content": "해저 잠수 함대 함장"}])
    assert "해저 잠수 함대" in msgs[1]["content"]
    got = writer.parse_reply('설명 {"title":"t","body":"b","anchor_script":"s"} 끝')
    assert got == {"title": "t", "body": "b", "anchor_script": "s"}
    assert not writer.numbers_match({"body": "득표율 99.9%", "anchor_script": ""}, f)


def test_keyword_search_prefers_candidate():
    docs = [{"doc_id": 1, "candidate_id": 1, "doc_type": "PLEDGE", "title": "윤별하 공약", "content": "초공간 셔틀 노선"},
            {"doc_id": 2, "candidate_id": 2, "doc_type": "PLEDGE", "title": "류해온 공약", "content": "바닷속 쓰레기 수거 로봇"}]
    assert retrieve.keyword_search(docs, "쓰레기 로봇", [2], k=1)[0]["doc_id"] == 2
    assert retrieve.keyword_search(docs, "셔틀", None, k=1)[0]["doc_id"] == 1


# ── 방송 엔진 ──
CUES = [dict(cue_id=i, order_no=i, segment_type=t, title=t, duration_sec=d, candidate_id=c) for i, t, d, c in [
    (1, "COUNTDOWN", 60, None), (2, "ANCHOR", 30, None), (3, "INTRO", 60, 1), (4, "INTRO", 60, 2), (5, "INTRO", 60, 3),
    (6, "LIVE", 660, None), (7, "INTERVIEW", 60, None), (8, "PROFILE", 60, None), (9, "LIVE", 140, None), (10, "CLOSING", 10, None)]]


def test_tc_sc_01_broadcast_order_with_elected():
    b = onair.Broadcast(CUES)
    t = 0.0
    b.start(t)
    media = lambda cue, cand: {"file_path": f"/static/media/{cue['segment_type'].lower()}_{cand}.mp4", "duration_sec": cue["duration_sec"]}
    queue = [{"queue_id": 1, "event_type": "RATE_MILESTONE", "candidate_id": 2, "duration_sec": 20},
             {"queue_id": 2, "event_type": "ELECTED", "candidate_id": 1, "duration_sec": 25}]
    seen = []
    for _ in range(60):
        n = b.next(t, lambda: queue.pop(0) if queue else None, media)
        seen.append((n.get("order_no"), n["kind"]))
        if n["kind"] == "END":
            break
        if n["kind"] == "ITEM":
            b.item_played(n["event_type"], n["candidate_id"])
        t += n.get("duration_sec") or n.get("wait") or 1
    orders = [o for o, k in seen if k in ("VIDEO", "ITEM")]
    assert orders[:5] == [1, 2, 3, 4, 5]
    assert 6 in orders and orders.index(7) > orders.index(6) and 8 in orders and 10 in orders
    assert [k for o, k in seen if o == 7] == ["VIDEO"]
    assert b.winner_id == 1 and b.status == "ENDED"


def test_tc_sc_05_skip_interview_when_no_winner():
    """BR-10: 당선 확정 전 데스크가 건너뛰면 인터뷰·이력 없이 최종 정리(9)로."""
    b = onair.Broadcast(CUES)
    b.start(0)
    b.idx = 5                                   # LIVE(6)로 이동
    b.cue_started = 0
    n = b.next(700, lambda: None, lambda c, x: None)
    assert n["kind"] == "BOARD" and n["overtime"]   # 시간이 지나도 당선 전이면 LIVE 유지
    b.skip(700)
    assert b.cue["order_no"] == 9


def test_pause_resume_does_not_eat_live_time():
    b = onair.Broadcast(CUES)
    b.start(0)
    b.idx, b.cue_started = 8, 0                 # 최종 정리 LIVE(9), 140초
    b.pause(10)
    assert b.next(100, lambda: None, lambda c, x: None)["kind"] == "PAUSE"
    b.resume(200)
    assert abs(b.cue_elapsed(210) - 20) < 0.01


def test_urgent_priority_first_and_in_press_order():
    """긴급 승인·큐시트 긴급은 당선 기사보다도 앞, 긴급끼리는 누른(승인한) 순서."""
    from datetime import datetime, timedelta
    from app.logic import rules
    t = datetime(2026, 11, 25, 21, 0, 0)
    items = [
        {"queue_id": 1, "priority": rules.priority("ELECTED"), "approved_at": t},
        {"queue_id": 2, "priority": rules.priority("RATE_MILESTONE", urgent=True), "approved_at": t + timedelta(seconds=20)},
        {"queue_id": 3, "priority": rules.priority("RATE_MILESTONE"), "approved_at": t - timedelta(seconds=60)},
        {"queue_id": 4, "priority": rules.priority("LEAD_CHANGE", urgent=True), "approved_at": t + timedelta(seconds=5)},
    ]
    assert [i["queue_id"] for i in sorted(items, key=rules.queue_sort_key)] == [4, 2, 1, 3]
