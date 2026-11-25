"""방송국 서버 (M=8101, K=8102 — 같은 코드)

uvicorn app.main:app --port 8101 --env-file .env.m --timeout-graceful-shutdown 2
  - 실시간 개표 웹: http://localhost:8101/          (누구나)
  - 로그인:        http://localhost:8101/login     (기자·데스크)
  - 송출 화면:     http://localhost:8101/onair/screen  (OBS 브라우저 소스, 1920×1080)
  - API 문서:      http://localhost:8101/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config, tasks, timing
from .db import SessionLocal, init_db
from .models import User
from .routers import articles, auth, desk, onair, pages, public, sync
from .workers import sync_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("station")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    tasks.set_loop(loop)
    # Windows에서 브라우저가 영상·음악 요청을 중간에 끊으면 'WinError 10054' 오류가 찍힘 — 무해하므로 숨김
    default_handler = loop.get_exception_handler()
    def quiet_reset(lp, context):
        if isinstance(context.get("exception"), (ConnectionResetError, ConnectionAbortedError)):
            return
        if default_handler:
            default_handler(lp, context)
        else:
            lp.default_exception_handler(context)
    loop.set_exception_handler(quiet_reset)
    # 벡터 검색(Chroma) 준비는 처음 한 번 몇 초 걸림 → 미리 스레드에서 (첫 기사 때 멈춤 방지)
    from .rag import _chroma
    loop.run_in_executor(None, _chroma)
    config.require("SECRET_KEY", "DEFAULT_PASSWORD", *(["NEC_API_KEY"] if config.SYNC_ENABLED else []))
    init_db()
    for d in (config.MEDIA_DIR, config.TTS_DIR, config.AVATAR_DIR):
        d.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        empty = db.query(User).count() == 0
    if empty or config.DEMO_MODE:          # 처음 켰거나 클라우드 시연 모드면 초기 데이터
        import seed
        seed.run(quiet=True)
        log.info("초기 데이터(seed) 넣음")
    task = asyncio.create_task(sync_worker.loop_forever()) if config.SYNC_ENABLED else None
    watcher = asyncio.create_task(timing.watch_loop())
    yield
    watcher.cancel()
    if task:
        task.cancel()


app = FastAPI(title=f"station-onair · {config.STATION_NAME}", version="1.0", lifespan=lifespan,
              description="실시간 개표 수신 · AI 기사 초안 · 기자 송고 · 데스크 승인 · 실시간 웹 · 20분 송출")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, session_cookie=f"onair_{config.STATION_CODE.lower()}",
                   same_site="lax", max_age=60 * 60 * 12)
timing.install_middleware(app)
app.mount("/static", StaticFiles(directory=str(config.APP_DIR / "static")), name="static")
for r in (auth.router, sync.router, articles.router, desk.router, public.router, onair.router, pages.router):
    app.include_router(r)


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True, "station": config.STATION_CODE, "sync_fail_count": sync_worker.state.fail_count}
