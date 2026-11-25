"""SSE(서버가 보내 주는 이벤트) 방송실 — 채널별로 연결된 브라우저에 알림을 뿌림.

채널: public(웹), newsroom(기자·데스크), onair(송출 화면·큐시트)
"""
import asyncio
import json

from fastapi.responses import StreamingResponse

HEARTBEAT_SEC = 15


class Broker:
    def __init__(self):
        self.subs: dict[str, set[asyncio.Queue]] = {}

    def publish(self, channel: str, event: str, data: dict):
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
        from .tasks import MAIN_LOOP
        try:
            in_loop = asyncio.get_running_loop() is MAIN_LOOP or MAIN_LOOP is None
        except RuntimeError:
            in_loop = MAIN_LOOP is None
        for q in list(self.subs.get(channel, ())):
            if in_loop:
                self._put(q, msg)
            else:                      # 요청 처리 스레드에서 부른 경우 → 루프 스레드에 맡김
                MAIN_LOOP.call_soon_threadsafe(self._put, q, msg)

    @staticmethod
    def _put(q: asyncio.Queue, msg: str):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    async def _stream(self, channel: str, request):
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.subs.setdefault(channel, set()).add(q)
        try:
            yield "retry: 3000\n\n"            # 끊기면 3초 뒤 브라우저가 스스로 다시 연결 (TC-SYS-05)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    yield await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SEC)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            self.subs.get(channel, set()).discard(q)

    def response(self, channel: str, request) -> StreamingResponse:
        return StreamingResponse(self._stream(channel, request), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


broker = Broker()
