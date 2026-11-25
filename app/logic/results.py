"""개표 결과 계산과 이벤트 감지 (FN-03-01 · FN-03-02) — 표준 라이브러리만 사용.

snapshot = 구별 최신 집계  {"STAR": {"counted_rate": 51.3, "counted_votes": 27000, "votes": {1: 12000, 2: 11000, 3: 3500}}, ...}
electors = 구별 선거인 수  {"STAR": 82000, ...}
"""
from __future__ import annotations

from dataclasses import dataclass, field

ALL = "ALL"
DEFAULT_TURNOUT = 0.65
ALL_MILESTONES = (10, 30, 50, 70, 90, 100)
REGION_MILESTONES = (50, 100)
LEAD_MIN_RATE = 5.0           # 개표 초반 몇 표 차이로 1위가 오가는 잡음은 무시
PRIORITY = {"RATE_MILESTONE": 5, "LEAD_CHANGE": 3, "WIN_LIKELY": 2, "WIN_SURE": 1, "ELECTED": 1}
WIN_LEVELS = ("WIN_LIKELY", "WIN_SURE", "ELECTED")


@dataclass
class Summary:
    code: str
    counted_rate: float
    counted_votes: int
    ballots_est: float            # 전체 투표수 추정 (개표수 ÷ 개표율)
    votes: dict                   # {후보: 득표}
    order: list = field(default_factory=list)   # 득표 많은 순 후보 번호

    @property
    def valid(self) -> int:
        return sum(self.votes.values())

    @property
    def remaining(self) -> float:
        return max(0.0, self.ballots_est - self.counted_votes)

    @property
    def leader(self):
        return self.order[0] if self.order and self.votes.get(self.order[0], 0) > 0 else None

    @property
    def gap(self) -> int:
        if len(self.order) < 2:
            return 0
        return self.votes[self.order[0]] - self.votes[self.order[1]]

    def vote_rate(self, cid) -> float:
        return round(self.votes.get(cid, 0) / self.valid * 100, 2) if self.valid else 0.0

    def rank(self, cid) -> int:
        return self.order.index(cid) + 1 if cid in self.order else len(self.order) + 1


def _order(votes: dict) -> list:
    return sorted(votes, key=lambda k: (-votes[k], k))


def summarize(snapshot: dict, electors: dict, candidates: list) -> dict:
    """구별 + 전체(ALL) 요약. 아직 개표가 시작 안 된 구는 선거인 수 × 투표율 추정치로 계산."""
    out = {}
    known = {c: s for c, s in snapshot.items() if s.get("counted_rate", 0) > 0}
    turnout = DEFAULT_TURNOUT
    if known:
        b = sum(s["counted_votes"] / (s["counted_rate"] / 100) for s in known.values())
        e = sum(electors.get(c, 0) for c in known)
        turnout = b / e if e else DEFAULT_TURNOUT
    for code, ele in electors.items():
        s = snapshot.get(code, {})
        rate = float(s.get("counted_rate", 0) or 0)
        counted = int(s.get("counted_votes", 0) or 0)
        votes = {c: int(s.get("votes", {}).get(c, 0)) for c in candidates}
        est = counted / (rate / 100) if rate > 0 else ele * turnout
        out[code] = Summary(code, rate, counted, est, votes, _order(votes))
    total_votes = {c: sum(out[k].votes[c] for k in electors) for c in candidates}
    counted = sum(out[k].counted_votes for k in electors)
    est = sum(out[k].ballots_est for k in electors)
    rate = 100.0 if electors and all(out[k].counted_rate >= 100 for k in electors) else \
        (round(min(99.99, counted / est * 100), 2) if est else 0.0)
    out[ALL] = Summary(ALL, rate, counted, est, total_votes, _order(total_votes))
    return out


def win_level(s: Summary) -> str | None:
    """전체 결과의 당선 단계 (02 기능정의서 이벤트 표)."""
    if s.leader is None:
        return None
    if s.counted_rate >= 100 or s.gap > s.remaining:
        return "ELECTED"
    if s.gap > 0.6 * s.remaining:
        return "WIN_SURE"
    if s.counted_rate >= 50 and s.gap >= 0.3 * s.remaining:
        return "WIN_LIKELY"
    return None


def _payload(s: Summary, names: dict, extra: dict | None = None) -> dict:
    p = {"region": s.code, "counted_rate": s.counted_rate,
         "votes": {str(c): s.votes[c] for c in s.order},
         "vote_rates": {str(c): s.vote_rate(c) for c in s.order},
         "leader": s.leader, "leader_name": names.get(s.leader), "gap": s.gap, "remaining": round(s.remaining)}
    if extra:
        p.update(extra)
    return p


def detect(prev: dict, cur: dict, emitted: set, names: dict | None = None) -> list[dict]:
    """직전 요약(prev)과 지금 요약(cur)을 비교해 새 이벤트 목록을 돌려줌.

    emitted: 이미 기록한 한 번뿐인 이벤트 열쇠 (예: "RATE:ALL:30", "WIN:ELECTED") — 같은 변경분을 두 번 받아도 중복 없음.
    """
    names = names or {}
    events = []
    for code, s in cur.items():
        p = prev.get(code)
        p_rate = p.counted_rate if p else 0.0
        # 1) 개표율 구간 돌파 — 한 번에 여러 구간을 넘으면 가장 높은 구간만
        steps = ALL_MILESTONES if code == ALL else REGION_MILESTONES
        crossed = [m for m in steps if p_rate < m <= s.counted_rate and f"RATE:{code}:{m}" not in emitted]
        if crossed:
            m = max(crossed)
            for x in crossed:
                emitted.add(f"RATE:{code}:{x}")
            events.append({"event_type": "RATE_MILESTONE", "region_code": code, "candidate_id": s.leader,
                           "key": f"RATE:{code}:{m}", "payload": _payload(s, names, {"milestone": m})})
        # 2) 1위 변동
        if p and p.leader and s.leader and p.leader != s.leader and s.counted_rate >= LEAD_MIN_RATE:
            events.append({"event_type": "LEAD_CHANGE", "region_code": code, "candidate_id": s.leader, "key": None,
                           "payload": _payload(s, names, {"prev_leader": p.leader, "prev_leader_name": names.get(p.leader)})})
    # 3) 당선 단계 — 전체(ALL)만, 각 단계 한 번씩. 한 번에 여러 단계를 넘으면 가장 높은 단계만 기사로
    s = cur.get(ALL)
    lvl = win_level(s) if s else None
    if lvl:
        reached = WIN_LEVELS[: WIN_LEVELS.index(lvl) + 1]
        new = [x for x in reached if f"WIN:{x}" not in emitted]
        for x in new:
            emitted.add(f"WIN:{x}")
        if lvl in new:
            events.append({"event_type": lvl, "region_code": ALL, "candidate_id": s.leader, "key": f"WIN:{lvl}",
                           "payload": _payload(s, names)})
    return events
