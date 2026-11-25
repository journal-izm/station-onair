"""백그라운드 작업 띄우기 — 요청 처리 스레드(동기 함수)에서도 이벤트 루프에 작업을 넘길 수 있게."""
import asyncio

MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop):
    global MAIN_LOOP
    MAIN_LOOP = loop


def spawn(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        return loop.create_task(coro)
    if MAIN_LOOP is None:
        coro.close()
        raise RuntimeError("이벤트 루프가 아직 준비되지 않았습니다")
    return asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)
