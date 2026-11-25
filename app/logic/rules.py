"""업무 규칙 (03 기능정의서 BR) — 표준 라이브러리만 사용."""
from __future__ import annotations

from .results import PRIORITY, WIN_LEVELS

MAX_PENDING = 3          # BR-05: 미처리 초안이 이만큼 쌓인 기자는 건너뜀
CHARS_PER_SEC = 6        # 한국어 낭독 속도 (글자 수 ÷ 6 = 초)
TTS_MIN_RATIO = 0.7      # BR-08: 예상 길이의 70% 미만이면 끝 문장이 잘린 것으로 봄


def next_reporter(reporter_ids: list[int], last_id: int | None, pending: dict[int, int]) -> int:
    """BR-05 기자 배정: 1→2→3 차례로, 미처리 초안 3건 이상인 기자는 건너뜀. 모두 많으면 가장 적은 기자."""
    if not reporter_ids:
        raise ValueError("기자 계정이 없습니다")
    start = (reporter_ids.index(last_id) + 1) if last_id in reporter_ids else 0
    order = reporter_ids[start:] + reporter_ids[:start]
    for rid in order:
        if pending.get(rid, 0) < MAX_PENDING:
            return rid
    return min(order, key=lambda r: (pending.get(r, 0), order.index(r)))


EDITABLE = {"DRAFT", "REJECTED"}          # BR-03


def can_edit(status: str) -> bool:
    return status in EDITABLE


def can_submit(status: str) -> bool:
    return status in EDITABLE


def priority(event_type: str) -> int:
    """BR-07: 당선 관련 1 → 일반 5."""
    return PRIORITY.get(event_type, 5)


def queue_sort_key(item: dict):
    """BR-07: priority 다음 승인 시각 순."""
    return (item["priority"], item["approved_at"], item["queue_id"])


def stale_items(new: dict, waiting: list[dict]) -> list[int]:
    """BR-06: 같은 지역·같은 이벤트 유형의 더 새로운 기사가 승인되면, 대기 중인 옛 기사는 건너뜀.
    (당선 단계 기사는 하나씩만 있으므로 해당 없음)"""
    if new["event_type"] in WIN_LEVELS:
        return []
    return [w["queue_id"] for w in waiting
            if w["queue_id"] != new["queue_id"] and w["region_code"] == new["region_code"]
            and w["event_type"] == new["event_type"] and w["status"] in ("PREPARING", "WAITING")
            and w["approved_at"] <= new["approved_at"]]


def expected_seconds(script: str) -> float:
    return len(script.replace(" ", "")) / CHARS_PER_SEC


def tts_ok(script: str, duration_sec: float | None) -> bool:
    """BR-08: 음성 길이가 예상의 70% 이상이어야 정상."""
    if not duration_sec:
        return False
    return duration_sec >= TTS_MIN_RATIO * expected_seconds(script)


def is_avatar_target(event_type: str) -> bool:
    """REQ-07-06: 당선 유력·확실·확정 기사만 립싱크 아바타."""
    return event_type in WIN_LEVELS


def avatar_decision(status: str | None, waited_sec: float, timeout_sec: float) -> str:
    """BR-11: READY면 AVATAR, 한도 안이면 WAIT, 실패·한도 초과면 TTS."""
    if status == "READY":
        return "AVATAR"
    if status in ("FAILED", "TIMEOUT") or waited_sec >= timeout_sec:
        return "TTS"
    return "WAIT"
