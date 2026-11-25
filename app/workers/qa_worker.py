"""시청자 질문 → 근거 검색(공식 자료 + 출고 기사) → AI 답변 초안 → 데스크 대기.

근거가 모자라면 답을 지어내지 않고 "공식 자료에서 확인되지 않습니다"로 둠 (환각 방지).
데스크가 승인하면 음성(TTS)을 만들고, 송출 화면이 읽을 기사가 없을 때 앵커가 답함.
"""
from __future__ import annotations

import asyncio
import logging

from .. import config
from ..db import SessionLocal
from ..logic import evidence as ev
from ..models import Article, ViewerQuestion
from ..sse import broker
from ..timing import Steps

log = logging.getLogger("qa")
_official: list[dict] | None = None


def official_docs() -> list[dict]:
    global _official
    if _official is None:
        _official = ev.load_official(config.OFFICIAL_DIR)
    return _official


def article_docs(db) -> list[dict]:
    rows = (db.query(Article).filter(Article.status == "APPROVED").order_by(Article.article_id.desc()).limit(50).all())
    return [{"kind": "ARTICLE", "id": f"A{a.article_id}", "title": a.title,
             "ref": f"출고 기사 #{a.article_id}" + (f" · {a.approved_at:%H:%M}" if a.approved_at else ""), "content": a.body}
            for a in rows]


def schedule(q_id: int):
    from ..tasks import spawn
    spawn(answer(q_id))


async def answer(q_id: int):
    st = Steps(f"시청자 질문 {q_id}")
    with SessionLocal() as db:
        q = db.get(ViewerQuestion, q_id)
        if not q:
            return
        text = q.question
        docs = official_docs() + article_docs(db)
    with st("근거검색"):
        evid = ev.find_evidence(text, docs, k=3)
    res, model = ev.template_answer(text, evid), "template"
    if evid and config.OPENAI_API_KEY:
        try:
            from .article_gen import call_llm
            with st("AI답변"):
                reply = await asyncio.to_thread(call_llm, ev.qa_messages(text, evid))
            res, model = ev.parse_qa_reply(reply, evid), config.LLM_MODEL
        except Exception as e:                       # AI 실패 → 근거 문장 그대로 (지어내지 않음)
            log.warning("시청자 질문 AI 답변 실패 → 근거 문장으로: %s", e)
    used = [evid[i - 1] for i in res["used"]] if res["grounded"] else []
    with SessionLocal() as db:
        q = db.get(ViewerQuestion, q_id)
        q.answer, q.grounded, q.ai_model, q.status = res["answer"], res["grounded"], model, "READY"
        q.sources = [{k: e[k] for k in ("kind", "title", "ref", "text", "highlight")} for e in used]
        db.commit()
    st.done(f"근거 {len(used)}개")
    broker.publish("newsroom", "qa.ready", {"q_id": q_id})


async def make_audio(q_id: int):
    """데스크 승인 뒤: '시청자 질문입니다 …' 음성 파일. 키가 없으면 송출 화면이 브라우저 음성으로 읽음."""
    if not config.OPENAI_API_KEY:
        return
    from .tts_worker import synth
    with SessionLocal() as db:
        q = db.get(ViewerQuestion, q_id)
        script = qa_script(q)
    config.TTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TTS_DIR / f"{config.STATION_CODE.lower()}_qa_{q_id}.wav"
    try:
        sec = await asyncio.to_thread(synth, script, path)
    except Exception as e:
        log.warning("시청자 질문 음성 실패 → 브라우저 음성: %s", e)
        with SessionLocal() as db:
            db.get(ViewerQuestion, q_id).audio_sec = -1
            db.commit()
        return
    with SessionLocal() as db:
        q = db.get(ViewerQuestion, q_id)
        q.audio_path, q.audio_sec = f"/static/tts/{path.name}", round(sec, 1)
        db.commit()


def qa_script(q: ViewerQuestion) -> str:
    return f"시청자 질문입니다. {q.nickname}님이 물었습니다. {q.question} {q.answer or ev.NOT_FOUND}"
