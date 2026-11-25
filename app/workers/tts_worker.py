"""FN-07-02 TTS · FN-07-07 아바타 — 승인 기사의 방송 원고를 송출할 수 있게 준비 (PREPARING → WAITING).

- OpenAI 키가 있으면: TTS_MODEL로 wav 생성 → 길이 확인(BR-08) → 짧으면 1회 다시 → 또 실패면 SKIPPED + 데스크 경고
- 키가 없으면: 송출 화면이 브라우저 음성(speechSynthesis)으로 읽음 (리허설·연습용)
- 당선 단계 기사 + 아바타 사용 시: 아바타 요청 → 90초(AVATAR_TIMEOUT_SEC) 안에 READY면 아바타, 아니면 TTS (BR-11)
"""
from __future__ import annotations

import asyncio
import logging
import time
import wave
from datetime import datetime

from .. import config
from ..db import SessionLocal
from ..logic import rules
from ..models import Article, AvatarVideo, OnairQueue, TtsAudio
from ..sse import broker
from . import avatar

log = logging.getLogger("tts")


def schedule(queue_id: int):
    from ..tasks import spawn
    spawn(prepare(queue_id))


def wav_seconds(path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def synth(script: str, out_path) -> float:
    """OpenAI TTS → wav 파일. 재생 길이(초)를 돌려줌 (스레드에서 실행)."""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=60)
    kwargs = dict(model=config.TTS_MODEL, voice=config.TTS_VOICE, input=script, response_format="wav")
    if config.TTS_INSTRUCTIONS:
        kwargs["instructions"] = config.TTS_INSTRUCTIONS
    with client.audio.speech.with_streaming_response.create(**kwargs) as r:
        r.stream_to_file(out_path)
    return wav_seconds(out_path)


async def make_tts(article: Article) -> TtsAudio | None:
    config.TTS_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in (1, 2):                      # BR-08: 1회 다시
        path = config.TTS_DIR / f"{config.STATION_CODE.lower()}_{article.article_id}_{attempt}.wav"
        try:
            dur = await asyncio.to_thread(synth, article.anchor_script, path)
            if rules.tts_ok(article.anchor_script, dur):
                return TtsAudio(article_id=article.article_id, voice=config.TTS_VOICE,
                                file_path=f"/static/tts/{path.name}", duration_sec=round(dur, 1))
            log.warning("TTS 길이 짧음 (기사 %s, %.1f초) — 다시 생성", article.article_id, dur)
        except Exception as e:
            log.warning("TTS 실패 (기사 %s, %d회): %s", article.article_id, attempt, e)
    return None


async def wait_avatar(article: Article) -> AvatarVideo | None:
    p = avatar.provider()
    if not p or not rules.is_avatar_target(article.event_type):
        return None
    av = AvatarVideo(article_id=article.article_id, provider=p.name, status="REQUESTED", requested_at=datetime.now())
    t0 = time.time()
    try:
        av.job_id = p.request(article.anchor_script)
    except Exception as e:
        log.warning("아바타 요청 실패: %s", e)
        av.status = "FAILED"
        return av
    while True:
        status, path, dur = p.check(av.job_id)
        decision = rules.avatar_decision(status, time.time() - t0, config.AVATAR_TIMEOUT_SEC)
        if decision == "AVATAR":
            av.status, av.file_path, av.duration_sec, av.ready_at = "READY", path, dur, datetime.now()
            return av
        if decision == "TTS":
            av.status = "FAILED" if status == "FAILED" else "TIMEOUT"
            return av
        await asyncio.sleep(2)


async def prepare(queue_id: int):
    with SessionLocal() as db:
        q = db.get(OnairQueue, queue_id)
        if not q or q.status != "PREPARING":
            return
        a = db.get(Article, q.article_id)
        art = Article(article_id=a.article_id, anchor_script=a.anchor_script, event_type=a.event_type)
    # 아바타와 TTS를 함께 준비 (아바타가 늦으면 TTS로 먼저 읽기 위해)
    av_task = asyncio.create_task(wait_avatar(art))
    tts = await make_tts(art) if config.OPENAI_API_KEY else None
    av = await av_task
    with SessionLocal() as db:
        q = db.get(OnairQueue, queue_id)
        if q.status != "PREPARING":          # 그사이 건너뛰기(SKIPPED)된 경우
            return
        if av:
            db.add(av)
            db.flush()
            q.avatar_id = av.avatar_id
        if tts:
            db.add(tts)
            db.flush()
            q.tts_id = tts.tts_id
        if config.OPENAI_API_KEY and not tts and not (av and av.status == "READY"):
            q.status = "SKIPPED"             # BR-08: 두 번 실패 → 건너뜀 (웹 게시는 그대로)
            db.commit()
            broker.publish("newsroom", "tts.failed", {"queue_id": queue_id, "article_id": q.article_id})
            broker.publish("onair", "tts.failed", {"queue_id": queue_id})
            return
        q.status = "WAITING"
        db.commit()
    broker.publish("onair", "queue.ready", {"queue_id": queue_id})
