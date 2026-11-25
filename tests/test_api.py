"""방송국 API 테스트 — 1차 확인 테스트케이스 번호와 같은 이름 (FastAPI·httpx 필요)."""
import asyncio
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ArticleReview, CountEvent, OnairQueue, ResultLatest, User  # noqa: E402
from app.workers import article_gen, sync_worker  # noqa: E402

PW = "pw-test"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(c: TestClient, who: str) -> TestClient:
    c.cookies.clear()
    r = c.post("/api/auth/login", json={"login_id": who, "password": PW})
    assert r.status_code == 200, r.text
    return c


def feed(rows):
    with SessionLocal() as db:
        return sync_worker.apply_rows(db, rows)


def make_article(c) -> dict:
    """가짜 개표 변경분 → 이벤트 → 틀 기사 초안 (OpenAI 없이)."""
    with SessionLocal() as db:
        _, last = sync_worker.snapshot(db)
    s = last + 1
    ids, _ = feed([{"seq": s, "code": "STAR", "counted_rate": 12.0 + s, "counted_votes": 6000 + 100 * s,
                    "votes": {"1": 2000 + 60 * s, "2": 3500 + 30 * s, "3": 400}}])
    assert ids, "이벤트가 생겨야 함"
    aid = asyncio.run(article_gen.generate(ids[0]))
    with SessionLocal() as db:
        from app.models import Article
        a = db.get(Article, aid)
        reporter = db.get(User, a.reporter_id).login_id
    return {"article_id": aid, "reporter": reporter}


def test_tc_rq_01_fixed_accounts(client):
    for who in ("reporter1", "reporter2", "reporter3", "desk1", "desk2"):
        login(client, who)
    assert client.post("/api/auth/login", json={"login_id": "nobody", "password": PW}).status_code == 401
    assert client.post("/api/auth/login", json={"login_id": "desk1", "password": "wrong"}).status_code == 401


def test_tc_rq_05_password_hashed(client):
    with SessionLocal() as db:
        assert all(PW not in u.password_hash and u.password_hash.startswith("pbkdf2$") for u in db.query(User))


def test_tc_db_03_and_04_results_and_events(client):
    ids, last = feed([{"seq": 1, "code": "STAR", "counted_rate": 12.0, "counted_votes": 6000,
                       "votes": {"1": 2800, "2": 2600, "3": 528}}])
    with SessionLocal() as db:
        assert db.query(ResultLatest).count() == 18
        n_events = db.query(CountEvent).count()
    again, _ = feed([{"seq": 1, "code": "STAR", "counted_rate": 12.0, "counted_votes": 6000,
                      "votes": {"1": 2800, "2": 2600, "3": 528}}])
    assert again == []
    with SessionLocal() as db:
        assert db.query(CountEvent).count() == n_events


def test_tc_rq_02_role_access(client):
    login(client, "reporter1")
    assert client.get("/api/desk/articles").status_code == 403
    assert client.get("/desk", follow_redirects=False).status_code in (302, 307)
    login(client, "desk1")
    assert client.post("/api/articles/1/submit").status_code == 403
    assert client.get("/api/articles").status_code == 403


def test_tc_api_05_article_permissions(client):
    a = make_article(client)
    client.cookies.clear()
    assert client.put(f"/api/articles/{a['article_id']}", json={"title": "t", "body": "b", "anchor_script": "s"}).status_code == 401
    other = next(r for r in ("reporter1", "reporter2", "reporter3") if r != a["reporter"])
    login(client, other)
    assert client.put(f"/api/articles/{a['article_id']}", json={"title": "t", "body": "b", "anchor_script": "s"}).status_code == 403
    login(client, a["reporter"])
    assert client.put(f"/api/articles/{a['article_id']}", json={"title": "고친 제목", "body": "본문", "anchor_script": "원고"}).status_code == 200


def test_tc_rq_03_and_api_06_approve_publish(client):
    a = make_article(client)
    client.cookies.clear()
    pub = lambda: [x["article_id"] for x in client.get("/api/public/articles").json()]
    assert a["article_id"] not in pub()                                    # DRAFT는 공개 안 됨
    login(client, a["reporter"])
    assert client.post(f"/api/articles/{a['article_id']}/submit").json()["status"] == "SUBMITTED"
    assert client.put(f"/api/articles/{a['article_id']}", json={"title": "x", "body": "x", "anchor_script": "x"}).status_code == 409
    client.cookies.clear()
    assert a["article_id"] not in pub()                                    # SUBMITTED도 공개 안 됨
    login(client, "desk1")
    r = client.post(f"/api/desk/articles/{a['article_id']}/approve", json={"comment": ""})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    login(client, "desk2")
    assert client.post(f"/api/desk/articles/{a['article_id']}/approve", json={}).status_code == 409   # TC-FN-06
    client.cookies.clear()
    assert pub()[0] == a["article_id"]
    with SessionLocal() as db:
        assert db.query(ArticleReview).filter_by(article_id=a["article_id"]).count() == 1


def test_tc_db_05_reject_then_approve(client):
    a = make_article(client)
    login(client, a["reporter"])
    client.post(f"/api/articles/{a['article_id']}/submit")
    login(client, "desk1")
    assert client.post(f"/api/desk/articles/{a['article_id']}/reject", json={"comment": ""}).status_code == 422
    assert client.post(f"/api/desk/articles/{a['article_id']}/reject", json={"comment": "숫자 확인"}).json()["status"] == "REJECTED"
    login(client, a["reporter"])
    assert client.post(f"/api/articles/{a['article_id']}/submit").json()["status"] == "SUBMITTED"
    login(client, "desk2")
    client.post(f"/api/desk/articles/{a['article_id']}/approve", json={})
    with SessionLocal() as db:
        rv = db.query(ArticleReview).filter_by(article_id=a["article_id"]).order_by(ArticleReview.review_id).all()
        assert [r.action for r in rv] == ["REJECT", "APPROVE"] and rv[0].comment == "숫자 확인"


def test_tc_api_07_public_results(client):
    client.cookies.clear()
    assert client.get("/api/public/results").status_code == 200
    for code in ("STAR", "DEEP", "DUNE", "NEBULA", "ORBIT", "ALL"):
        assert client.get(f"/api/public/results/{code}").status_code == 200
    assert client.get("/api/public/results/XYZ").status_code == 404


def test_tc_api_09_onair_next_and_done(client):
    login(client, "desk1")
    deadline = time.time() + 5                     # TTS 준비(키 없음 → 브라우저 음성)가 끝나 WAITING이 되길 기다림
    while time.time() < deadline:
        with SessionLocal() as db:
            if db.query(OnairQueue).filter_by(status="WAITING").count():
                break
        time.sleep(0.2)
    client.post("/api/onair/control", json={"action": "reset"})
    client.post("/api/onair/control", json={"action": "start"})
    kinds = []
    for _ in range(12):                            # 영상 구간 5개(파일 없음 → SLATE) 뒤 LIVE
        n = client.get("/api/onair/next").json()
        kinds.append(n["kind"])
        if n["kind"] == "ITEM":
            assert n["media"] == "SPEECH" and n["script"]
            assert client.post(f"/api/onair/queue/{n['queue_id']}/done", json={"result": "DONE"}).json()["status"] == "DONE"
            break
    assert kinds[:5] == ["SLATE"] * 5 and "ITEM" in kinds
    assert client.get("/api/onair/next").json()["kind"] in ("ITEM", "BOARD")   # 대기열이 비면 전체 현황 (BR-09)
