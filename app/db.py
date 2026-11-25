"""DB 연결 — SQLAlchemy. STATION_DB_URL만 바꾸면 PostgreSQL로도 옮길 수 있음."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DB_URL

_is_sqlite = DB_URL.startswith("sqlite")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False, "timeout": 15} if _is_sqlite else {})

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns():
    """예전에 만든 DB 파일에 새 칸 추가 (create_all은 이미 있는 표에 칸을 안 더해 줌)."""
    from sqlalchemy import inspect, text
    cols = {c["name"] for c in inspect(engine).get_columns("article")}
    if "urgent" not in cols:
        with engine.begin() as con:
            con.execute(text("ALTER TABLE article ADD COLUMN urgent BOOLEAN NOT NULL DEFAULT 0"))
