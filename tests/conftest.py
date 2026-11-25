"""API 테스트 준비 — 임시 DB, 선관위 수신 끔, OpenAI 키 없음(틀 기사·브라우저 음성)."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update({"STATION_DB_URL": f"sqlite:///{_tmp}/test_station.db", "STATION_CODE": "T", "SYNC_ENABLED": "false",
                   "OPENAI_API_KEY": "", "DEFAULT_PASSWORD": "pw-test", "SECRET_KEY": "test", "DEMO_MODE": "false",
                   "AVATAR_PROVIDER": "none", "ENV_FILE": ".env.none"})
