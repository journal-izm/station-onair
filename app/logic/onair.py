"""20분 방송 진행 엔진 (FN-07-01 · 03 · 05 · 06) — 표준 라이브러리만 사용, 시간(now)은 밖에서 넣음.

송출 화면은 한 항목을 다 재생할 때마다 next()를 부르고, 엔진은 다음에 틀 것을 알려 줌.
  VIDEO : 사전 제작 영상 (카운트다운·오프닝·후보 소개·인터뷰·이력·마무리)
  SLATE : 영상 파일이 없을 때 제목만 보여 주는 화면 (길이만큼)
  ITEM  : 승인 기사 낭독 (TTS·아바타·브라우저 음성) — 대기열에서 꺼냄
  BOARD : 읽을 기사가 없을 때 전체 현황 차트 + 배경음악 (BR-09)
  PAUSE / IDLE / END
"""
from __future__ import annotations

from typing import Callable

VIDEO_TYPES = {"COUNTDOWN", "ANCHOR", "INTRO", "INTERVIEW", "PROFILE", "CLOSING"}
WINNER_TYPES = {"INTERVIEW", "PROFILE"}
BOARD_WAIT = 4.0


class Broadcast:
    def __init__(self, cues: list[dict]):
        """cues: [{"cue_id", "order_no", "segment_type", "title", "duration_sec", "candidate_id"(INTRO만)}] 순서대로."""
        self.cues = sorted(cues, key=lambda c: c["order_no"])
        self.status = "STANDBY"          # STANDBY / ON_AIR / PAUSED / ENDED
        self.idx = 0
        self.cue_started: float | None = None
        self.cue_paused_total = 0.0
        self.paused_at: float | None = None
        self.played_video = False
        self.elected_played = False
        self.winner_id: int | None = None
        self.started_at: float | None = None
        self.log: list[str] = []

    # ── 현재 구간 ──
    @property
    def cue(self) -> dict | None:
        return self.cues[self.idx] if 0 <= self.idx < len(self.cues) else None

    def cue_elapsed(self, now: float) -> float:
        if self.cue_started is None:
            return 0.0
        paused = self.cue_paused_total + ((now - self.paused_at) if self.paused_at else 0)
        return max(0.0, now - self.cue_started - paused)

    def _enter(self, idx: int, now: float):
        self.idx = idx
        self.cue_started, self.cue_paused_total, self.played_video = now, 0.0, False
        if self.cue:
            self.log.append(f"구간 {self.cue['order_no']} {self.cue['title']}")
        else:
            self.status = "ENDED"
            self.log.append("방송 끝")

    def _index_of(self, order_no: int) -> int:
        for i, c in enumerate(self.cues):
            if c["order_no"] == order_no:
                return i
        return len(self.cues)

    def _advance(self, now: float):
        cur = self.cue
        nxt = self.idx + 1
        # 당선 확정이 안 나왔으면 인터뷰·이력 구간은 건너뜀 (BR-10)
        while nxt < len(self.cues) and self.cues[nxt]["segment_type"] in WINNER_TYPES and self.winner_id is None:
            nxt += 1
        if cur:
            self.log.append(f"구간 {cur['order_no']} 끝")
        self._enter(nxt, now)

    def _first_live(self, cue: dict) -> bool:
        lives = [c for c in self.cues if c["segment_type"] == "LIVE"]
        return bool(lives) and lives[0]["cue_id"] == cue["cue_id"]

    # ── 제어 (API-07-04) ──
    def start(self, now: float):
        if self.status in ("STANDBY", "ENDED"):
            self.__init__(self.cues)
            self.status, self.started_at = "ON_AIR", now
            self._enter(0, now)

    def pause(self, now: float):
        if self.status == "ON_AIR":
            self.status, self.paused_at = "PAUSED", now

    def resume(self, now: float):
        if self.status == "PAUSED":
            self.cue_paused_total += now - (self.paused_at or now)
            self.status, self.paused_at = "ON_AIR", None

    def skip(self, now: float):
        """다음 구간으로. 첫 LIVE에서 당선 확정 전이면 인터뷰·이력을 건너뛰고 최종 정리로 (BR-10)."""
        if self.status not in ("ON_AIR", "PAUSED") or not self.cue:
            return
        self.resume(now)
        self._advance(now)

    # ── 기사 낭독 결과 보고 ──
    def item_played(self, event_type: str, candidate_id: int | None):
        if event_type == "ELECTED":
            self.elected_played = True
            self.winner_id = candidate_id

    # ── 다음 항목 (API-07-02) ──
    def next(self, now: float, pop_item: Callable[[], dict | None], media: Callable[[dict, int | None], dict | None]) -> dict:
        for _ in range(len(self.cues) + 2):   # 구간을 넘기며 찾되 무한 반복은 막음
            if self.status in ("STANDBY",):
                return {"kind": "IDLE"}
            if self.status == "ENDED" or self.cue is None:
                self.status = "ENDED"
                return {"kind": "END"}
            if self.status == "PAUSED":
                return {"kind": "PAUSE"}
            cue = self.cue
            st = cue["segment_type"]
            base = {"cue_id": cue["cue_id"], "order_no": cue["order_no"], "segment": st, "title": cue["title"]}
            if st in VIDEO_TYPES:
                if self.played_video:
                    self._advance(now)
                    continue
                self.played_video = True
                cand = self.winner_id if st in WINNER_TYPES else cue.get("candidate_id")
                m = media(cue, cand)
                if m:
                    return {**base, "kind": "VIDEO", "src": m["file_path"], "duration_sec": m.get("duration_sec") or cue["duration_sec"]}
                return {**base, "kind": "SLATE", "duration_sec": cue["duration_sec"]}
            # LIVE 구간
            first = self._first_live(cue)
            if first and self.elected_played:
                self._advance(now)
                continue
            left = cue["duration_sec"] - self.cue_elapsed(now)
            if left <= 0 and not first:
                self._advance(now)
                continue
            item = pop_item()
            if item:
                return {**base, "kind": "ITEM", **item}
            return {**base, "kind": "BOARD", "wait": BOARD_WAIT if first or left <= 0 else min(BOARD_WAIT, max(1.0, left)),
                    "overtime": left <= 0}
        return {"kind": "END"}

    def snapshot(self, now: float) -> dict:
        cue = self.cue
        return {"status": self.status, "current_cue": cue["order_no"] if cue else None,
                "cue_title": cue["title"] if cue else None, "cue_elapsed": round(self.cue_elapsed(now), 1),
                "elapsed": round(now - self.started_at, 1) if self.started_at else 0,
                "elected_played": self.elected_played, "winner_id": self.winner_id}
