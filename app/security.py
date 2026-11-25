"""FN-01 로그인·역할 확인 — 비밀번호는 해시(PBKDF2, 표준 라이브러리)로만 저장 (NFR-02)."""
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

ITER = 200_000


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), ITER).hex()
    return f"pbkdf2${ITER}${salt}${h}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except Exception:
        return False


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "로그인이 필요합니다")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "이 기능을 쓸 권한이 없습니다")
        return user
    return dep


reporter_only = require_role("REPORTER")
desk_only = require_role("DESK")
staff = require_role("REPORTER", "DESK")
