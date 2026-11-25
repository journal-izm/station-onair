"""FN-04-01 · 02 — 이벤트 → 기사 초안(gpt-6-luna + 후보 자료 검색) → 기자 자동 배정."""
from __future__ import annotations

import asyncio
import logging

from .. import config, rag
from ..db import SessionLocal
from ..logic import rules, writer
from ..models import Article, Candidate, CountEvent, PromptTemplate, Region, User
from ..sse import broker

log = logging.getLogger("article")
_sem = asyncio.Semaphore(3)          # 한꺼번에 AI를 부르는 수 제한
stats = {"ai_ok": 0, "ai_fail": 0, "template": 0, "last_error": None}


def schedule(event_id: int):
    from ..tasks import spawn
    spawn(generate(event_id))


def call_llm(messages: list[dict]) -> str:
    """OpenAI 호출 (스레드에서 실행). 모델은 .env의 LLM_MODEL(gpt-6-luna)."""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.LLM_TIMEOUT_SEC)
    r = client.chat.completions.create(model=config.LLM_MODEL, messages=messages,
                                       response_format={"type": "json_object"})
    return r.choices[0].message.content or ""


def assign_reporter(db) -> int:
    """BR-05 — 마지막 배정 기자 다음 사람, 미처리 3건 이상은 건너뜀."""
    reporters = [u.user_id for u in db.query(User).filter_by(role="REPORTER").order_by(User.user_id)]
    last = db.query(Article.reporter_id).order_by(Article.article_id.desc()).limit(1).scalar()
    pending = {rid: db.query(Article).filter(Article.reporter_id == rid, Article.status.in_(("DRAFT", "REJECTED"))).count()
               for rid in reporters}
    return rules.next_reporter(reporters, last, pending)


async def generate(event_id: int) -> int | None:
    async with _sem:
        with SessionLocal() as db:
            ev = db.get(CountEvent, event_id)
            if not ev or db.query(Article).filter_by(event_id=event_id).first():
                return None
            regions = {r.region_code: r.name for r in db.query(Region)}
            cands = {c.candidate_id: c.name for c in db.query(Candidate)}
            event = {"event_type": ev.event_type, "region_code": ev.region_code, "payload": ev.payload}
            f = writer.facts(event, regions, cands)
            ids = [x for x in (ev.candidate_id, ev.payload.get("prev_leader")) if x]
            query = f"{f['event_ko']} {f['leader_name']} 이력 공약"
            docs = rag.search(db, query, ids or None, k=3)
            tpl = db.query(PromptTemplate).filter_by(event_type=ev.event_type, active=True).first()
            art, model = None, "template"
            if config.OPENAI_API_KEY:
                try:
                    msgs = writer.build_messages(tpl.system_prompt if tpl else None, tpl.user_prompt if tpl else None, f, docs)
                    text = await asyncio.to_thread(call_llm, msgs)
                    art = writer.parse_reply(text)
                    if not writer.numbers_match(art, f):
                        raise ValueError("AI 기사 숫자가 실제 개표 수치와 다름")
                    model = config.LLM_MODEL
                    stats["ai_ok"] += 1
                except Exception as e:     # TC-SYS-04: 실패해도 수신·웹·송출은 계속
                    stats["ai_fail"] += 1
                    stats["last_error"] = f"{e.__class__.__name__}: {str(e)[:150]}"
                    log.warning("기사 생성 실패 (event %s): %s", event_id, stats["last_error"])
                    art = None
            if art is None:
                if config.LLM_FALLBACK != "template":
                    broker.publish("newsroom", "article.failed", {"event_id": event_id, "error": stats["last_error"]})
                    return None
                art = writer.template_article(f)
                stats["template"] += 1
            reporter = assign_reporter(db)
            a = Article(event_id=event_id, region_code=ev.region_code, title=art["title"][:100], body=art["body"],
                        anchor_script=art["anchor_script"], status="DRAFT", reporter_id=reporter,
                        rag_sources=[d["doc_id"] for d in docs], ai_model=model, event_type=ev.event_type)
            db.add(a)
            db.commit()
            aid = a.article_id
        broker.publish("newsroom", "article.assigned", {"article_id": aid, "reporter_id": reporter})
        if config.DEMO_MODE and config.DEMO_AUTO_APPROVE:
            from .. import services
            await services.demo_auto_publish(aid)
        return aid
