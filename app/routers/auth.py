"""영역 01 계정·인증 — API-01-01 ~ 03."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["01 계정·인증"])


class Login(BaseModel):
    login_id: str
    password: str


def _me(u: User) -> dict:
    return {"user_id": u.user_id, "login_id": u.login_id, "name": u.name, "role": u.role}


@router.post("/login", summary="API-01-01 로그인")
def login(body: Login, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(login_id=body.login_id).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않습니다")
    request.session["user_id"] = u.user_id
    return _me(u)


@router.post("/logout", summary="API-01-02 로그아웃")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", summary="API-01-03 내 정보·역할")
def me(user: User = Depends(current_user)):
    return _me(user)
