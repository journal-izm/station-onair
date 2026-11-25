"""화면(HTML) — SCR-01-01 ~ SCR-07-02. 데이터는 화면 안의 자바스크립트가 API로 가져옴."""
from urllib.parse import quote
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import config
from ..db import SessionLocal
from ..models import User

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
HOME = {"REPORTER": "/reporter", "DESK": "/desk"}


def _user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    with SessionLocal() as db:
        return db.get(User, uid)


def page(request: Request, name: str, roles: tuple | None = None, **ctx):
    user = _user(request)
    if roles is not None and (not user or user.role not in roles):
        nxt = request.url.path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse("/login?next=" + quote(nxt))   # TC-RQ-02: 권한 없는 화면 → 로그인 (로그인 뒤 원래 화면으로)
    return templates.TemplateResponse(request, name, {"station": config.STATION_NAME, "code": config.STATION_CODE,
                                                      "other": config.OTHER_STATION_URL, "user": user, **ctx})


@router.get("/", response_class=HTMLResponse)
def public_home(request: Request):
    return page(request, "public.html")                      # SCR-06-01 (누구나)


@router.get("/region/{code}", response_class=HTMLResponse)
def region_page(request: Request, code: str):
    return page(request, "region.html", region=code)         # SCR-06-02


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return page(request, "ask.html")                         # 시청자 질문 (송출 화면 QR로 들어옴, 누구나)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = _user(request)
    if user:
        return RedirectResponse(HOME[user.role])
    return page(request, "login.html")                       # SCR-01-01


@router.get("/reporter", response_class=HTMLResponse)
def reporter_page(request: Request):
    return page(request, "reporter.html", ("REPORTER",))     # SCR-04-01 · 04-02


@router.get("/desk", response_class=HTMLResponse)
def desk_page(request: Request):
    return page(request, "desk.html", ("DESK",))             # SCR-05-01 · 05-02


@router.get("/monitor", response_class=HTMLResponse)
def monitor_page(request: Request):
    return page(request, "monitor.html", ("DESK",))          # SCR-03-01


@router.get("/onair/control", response_class=HTMLResponse)
def onair_control_page(request: Request):
    return page(request, "onair_control.html", ("DESK",))    # SCR-07-02


@router.get("/onair/screen", response_class=HTMLResponse)
def onair_screen_page(request: Request):
    return page(request, "onair_screen.html", ("DESK",))     # SCR-07-01 (송출 PC에서 데스크 로그인 후 OBS로 캡처)
