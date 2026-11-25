"""방송국 서버 실행 설정 — M·K가 같은 코드, .env.m / .env.k 로 나눔 (08 개발환경 '실행 설정').

uvicorn app.main:app --port 8101 --env-file .env.m --timeout-graceful-shutdown 2   (M 방송국)
uvicorn app.main:app --port 8102 --env-file .env.k --timeout-graceful-shutdown 2   (K 방송국)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].strip().strip('"').strip("'")     # 값 뒤 주석은 버림
            os.environ.setdefault(k.strip(), v)


_load_dotenv(BASE_DIR / (os.getenv("ENV_FILE") or ".env"))


def _env(name: str, default: str = "") -> str:
    """환경 변수 읽기. .env에 'NAME=' 처럼 값이 비어 있으면 기본값을 씀."""
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


def _bool(v) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")


STATION_CODE = _env("STATION_CODE", "M")
STATION_NAME = _env("STATION_NAME", f"{STATION_CODE} 방송국")
OTHER_STATION_URL = _env("OTHER_STATION_URL", "")
DB_URL = _env("STATION_DB_URL", f"sqlite:///{(BASE_DIR / ('station_' + STATION_CODE.lower() + '.db')).as_posix()}")
SECRET_KEY = _env("SECRET_KEY", "dev-secret-change-me")
DEFAULT_PASSWORD = _env("DEFAULT_PASSWORD", "onair2026")   # seed가 계정 5개에 넣는 처음 비밀번호

NEC_BASE_URL = _env("NEC_BASE_URL", "http://localhost:8000").rstrip("/")
NEC_API_KEY = _env("NEC_API_KEY", "")
ELECTION_ID = _env("ELECTION_ID", "HANBIT-2026")
SYNC_INTERVAL_SEC = float(_env("SYNC_INTERVAL_SEC", "5"))
SYNC_ENABLED = _bool(_env("SYNC_ENABLED", "true"))

OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
LLM_MODEL = _env("LLM_MODEL", "gpt-6-luna")
LLM_TIMEOUT_SEC = float(_env("LLM_TIMEOUT_SEC", "40"))
LLM_FALLBACK = _env("LLM_FALLBACK", "template")    # template = AI 실패 시 틀 기사 / off = 실패로 기록만
EMBED_MODEL = _env("EMBED_MODEL", "text-embedding-3-small")
TTS_MODEL = _env("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = _env("TTS_VOICE", "alloy")
TTS_INSTRUCTIONS = _env("TTS_INSTRUCTIONS", "차분하고 또렷한 한국어 뉴스 앵커 말투로 읽어 주세요.")

AVATAR_PROVIDER = _env("AVATAR_PROVIDER", "none")   # none / mock (실제 서비스는 app/workers/avatar.py에 추가)
AVATAR_TIMEOUT_SEC = float(_env("AVATAR_TIMEOUT_SEC", "90"))
AVATAR_MOCK_DELAY_SEC = float(_env("AVATAR_MOCK_DELAY_SEC", "20"))

DEMO_MODE = _bool(_env("DEMO_MODE", "false"))
DEMO_AUTO_APPROVE = _bool(_env("DEMO_AUTO_APPROVE", "false"))   # 시연 모드에서 자동 송고·승인 (사람 검수 생략 → 시연 전용)

MEDIA_DIR = APP_DIR / "static" / "media"
TTS_DIR = APP_DIR / "static" / "tts"
AVATAR_DIR = APP_DIR / "static" / "avatar"
VECTOR_DIR = BASE_DIR / "vectordb"


def require(*names: str) -> None:
    """꼭 필요한 값이 .env에 없으면 무엇이 없는지 알려 주고 멈춤 (TC-ENV-02)."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise SystemExit(f"[설정 오류] .env에 다음 값이 없습니다: {', '.join(missing)}  (.env.example 참고)")


if "://" not in DB_URL and DB_URL.endswith(".db"):      # 파일 이름만 적어도 됨 (예: station_m.db)
    DB_URL = f"sqlite:///{(BASE_DIR / DB_URL).as_posix()}"
if "://" not in DB_URL:
    raise SystemExit(f"[설정 오류] DB 주소가 이상합니다: {DB_URL!r} — .env의 DB 주소 칸을 비우거나 sqlite:///파일이름.db 형식으로 적으세요")
