"""방송국 서버 실행 설정 — M·K가 같은 코드, .env.m / .env.k 로 나눔 (08 개발환경 '실행 설정').

uvicorn app.main:app --port 8101 --env-file .env.m   (M 방송국)
uvicorn app.main:app --port 8102 --env-file .env.k   (K 방송국)
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
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / os.getenv("ENV_FILE", ".env"))


def _bool(v) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")


STATION_CODE = os.getenv("STATION_CODE", "M")
STATION_NAME = os.getenv("STATION_NAME", f"{STATION_CODE} 방송국")
OTHER_STATION_URL = os.getenv("OTHER_STATION_URL", "")
DB_URL = os.getenv("STATION_DB_URL", f"sqlite:///{BASE_DIR / ('station_' + STATION_CODE.lower() + '.db')}")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "onair2026")   # seed가 계정 5개에 넣는 처음 비밀번호

NEC_BASE_URL = os.getenv("NEC_BASE_URL", "http://localhost:8000").rstrip("/")
NEC_API_KEY = os.getenv("NEC_API_KEY", "")
ELECTION_ID = os.getenv("ELECTION_ID", "HANBIT-2026")
SYNC_INTERVAL_SEC = float(os.getenv("SYNC_INTERVAL_SEC", "5"))
SYNC_ENABLED = _bool(os.getenv("SYNC_ENABLED", "true"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-6-luna")
LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "40"))
LLM_FALLBACK = os.getenv("LLM_FALLBACK", "template")    # template = AI 실패 시 틀 기사 / off = 실패로 기록만
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
TTS_INSTRUCTIONS = os.getenv("TTS_INSTRUCTIONS", "차분하고 또렷한 한국어 뉴스 앵커 말투로 읽어 주세요.")

AVATAR_PROVIDER = os.getenv("AVATAR_PROVIDER", "none")   # none / mock (실제 서비스는 app/workers/avatar.py에 추가)
AVATAR_TIMEOUT_SEC = float(os.getenv("AVATAR_TIMEOUT_SEC", "90"))
AVATAR_MOCK_DELAY_SEC = float(os.getenv("AVATAR_MOCK_DELAY_SEC", "20"))

DEMO_MODE = _bool(os.getenv("DEMO_MODE", "false"))
DEMO_AUTO_APPROVE = _bool(os.getenv("DEMO_AUTO_APPROVE", "false"))   # 시연 모드에서 자동 송고·승인 (사람 검수 생략 → 시연 전용)

MEDIA_DIR = APP_DIR / "static" / "media"
TTS_DIR = APP_DIR / "static" / "tts"
AVATAR_DIR = APP_DIR / "static" / "avatar"
VECTOR_DIR = BASE_DIR / "vectordb"
