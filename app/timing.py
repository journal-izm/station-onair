"""시간 측정 로그 (⏱) — 어디서 느려지는지 찾기 위한 것.

.env 설정
  TIMING_LOG=1          켜기 (기본 1, 0이면 끔)
  SLOW_REQUEST_MS=500   이보다 오래 걸린 웹 요청만 기록
  LOOP_LAG_MS=300       서버가 이만큼 이상 '멈춰 있으면' 기록 (다른 일을 못 하고 기다린 시간)

로그 예
  ⏱ 요청 느림 GET /api/desk/articles 820ms
  ⏱ 서버 멈춤 1340ms (이 시간 동안 모든 화면이 기다림)
  ⏱ 기사 생성 event 12 | 자료검색 410ms · AI작성 3200ms · 저장 15ms · 합계 3630ms
"""
import asyncio
import logging
import time
from contextlib import contextmanager

from . import config

log = logging.getLogger("timing")
ENABLED = config._env("TIMING_LOG", "1") != "0"
SLOW_REQUEST_MS = int(config._env("SLOW_REQUEST_MS", "500"))
LOOP_LAG_MS = int(config._env("LOOP_LAG_MS", "300"))


class Steps:
    """단계별 시간 재기: s = Steps('기사 생성 event 12'); with s('자료검색'): ...; s.done()"""
    def __init__(self, title: str):
        self.title, self.t0, self.parts = title, time.perf_counter(), []

    @contextmanager
    def __call__(self, name: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.parts.append((name, (time.perf_counter() - t) * 1000))

    def done(self, extra: str = ""):
        if not ENABLED:
            return
        total = (time.perf_counter() - self.t0) * 1000
        body = " · ".join(f"{n} {ms:.0f}ms" for n, ms in self.parts)
        log.info("⏱ %s | %s · 합계 %.0fms%s", self.title, body, total, f" ({extra})" if extra else "")


async def watch_loop():
    """0.1초마다 깨어나서 늦게 깼으면 = 그동안 서버가 다른 일에 붙잡혀 멈춰 있었음."""
    if not ENABLED:
        return
    while True:
        t = time.perf_counter()
        await asyncio.sleep(0.1)
        lag = (time.perf_counter() - t - 0.1) * 1000
        if lag >= LOOP_LAG_MS:
            log.warning("⏱ 서버 멈춤 %.0fms (이 시간 동안 모든 화면이 기다림)", lag)


def install_middleware(app):
    if not ENABLED:
        return

    @app.middleware("http")
    async def _time_requests(request, call_next):
        t = time.perf_counter()
        resp = await call_next(request)
        ms = (time.perf_counter() - t) * 1000
        path = request.url.path
        if ms >= SLOW_REQUEST_MS and not path.endswith("/stream") and not path.startswith("/static"):
            log.warning("⏱ 요청 느림 %s %s %.0fms", request.method, path, ms)
        return resp
