"""FN-07-07 립싱크 아바타 — 서비스마다 방식이 달라 '요청·확인' 두 함수만 맞추면 됩니다.

AVATAR_PROVIDER
  none : 아바타를 쓰지 않음 (모든 기사 TTS)
  mock : 연습용. AVATAR_MOCK_DELAY_SEC 뒤 static/avatar/sample.mp4가 있으면 READY, 없으면 FAILED
실제 서비스(HeyGen·D-ID 등)는 아래 Provider를 하나 더 만들어 PROVIDERS에 넣습니다. 가입 전 공식 가격을 꼭 확인하세요.
"""
from __future__ import annotations

import time

from .. import config


class MockProvider:
    name = "MOCK"

    def __init__(self):
        self.jobs: dict[str, float] = {}

    def request(self, script: str) -> str:
        job = f"mock-{len(self.jobs) + 1}-{int(time.time())}"
        self.jobs[job] = time.time()
        return job

    def check(self, job_id: str) -> tuple[str, str | None, float | None]:
        """(상태, 파일 경로, 길이) — 상태는 REQUESTED / READY / FAILED"""
        if time.time() - self.jobs.get(job_id, 0) < config.AVATAR_MOCK_DELAY_SEC:
            return "REQUESTED", None, None
        sample = config.AVATAR_DIR / "sample.mp4"
        return ("READY", "/static/avatar/sample.mp4", 20.0) if sample.exists() else ("FAILED", None, None)


PROVIDERS = {"mock": MockProvider}
_instance = None


def provider():
    global _instance
    if config.AVATAR_PROVIDER == "none":
        return None
    if _instance is None:
        cls = PROVIDERS.get(config.AVATAR_PROVIDER)
        _instance = cls() if cls else None
    return _instance
