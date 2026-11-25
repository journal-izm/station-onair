"""테스트 확인 도구 — DB에 들어간 값을 사람이 읽기 쉽게 보여 줌 (TEST_GUIDE의 수동 테스트용).

python tools/check.py --env .env.m counts          # TC-DB-01 · 03 표마다 행 수
python tools/check.py --env .env.m events          # TC-SC-02 · FN-02 · FN-03 · DB-04 감지한 이벤트
python tools/check.py --env .env.m article 3       # TC-FN-10 · DB-05 기사 한 건 자세히
python tools/check.py --env .env.m latency         # TC-RQ-04 승인 → 음성 준비까지 걸린 시간
python tools/check.py --env .env.m queue           # TC-DB-06 · FN-07 방송 대기열
python tools/check.py --env .env.m llm             # TC-ENV-06 gpt-6-luna 연결
python tools/check.py --env .env.m tts "문장"       # TC-ENV-07 TTS 연결과 발음
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
args = sys.argv[1:]
if len(args) >= 2 and args[0] == "--env":
    os.environ["ENV_FILE"] = args[1]
    args = args[2:]

from app import config  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.logic import rules  # noqa: E402
from app.models import (Article, ArticleReview, Candidate, CandidateDoc, CountEvent, CueSheet, OnairQueue,  # noqa: E402
                        Region, ResultLatest, TtsAudio, User)

N = {"RATE_MILESTONE": "개표율", "LEAD_CHANGE": "1위 변동", "WIN_LIKELY": "당선 유력", "WIN_SURE": "당선 확실", "ELECTED": "당선 확정"}


def line(*cols, w=(6, 10, 12, 8, 8)):
    print("  ".join(str(c).ljust(w[i] if i < len(w) else 10) for i, c in enumerate(cols)))


def counts(db):
    print(f"[{config.STATION_NAME}] DB = {config.DB_URL}")
    for name, q in [("계정 users", db.query(User)), ("후보 candidate", db.query(Candidate)),
                    ("지역 region(전체 포함)", db.query(Region)), ("후보 자료 candidate_doc", db.query(CandidateDoc)),
                    ("큐시트 cue_sheet", db.query(CueSheet)), ("최신 결과 result_latest", db.query(ResultLatest)),
                    ("이벤트 count_event", db.query(CountEvent))]:
        print(f"  {name:28} {q.count():>4}")
    st = {}
    for (s,) in db.query(Article.status):
        st[s] = st.get(s, 0) + 1
    print(f"  {'기사 article':28} {sum(st.values()):>4}  {st}")
    qs = {}
    for (s,) in db.query(OnairQueue.status):
        qs[s] = qs.get(s, 0) + 1
    print(f"  {'방송 대기열 onair_queue':28} {sum(qs.values()):>4}  {qs}")
    print("\n  기대값(처음): 계정 5 · 후보 3 · 지역 6 · 후보 자료 12 · 큐시트 10 · 수신 뒤 최신 결과 18")


def events(db):
    names = {r.region_code: r.name for r in db.query(Region)}
    cands = {c.candidate_id: c.name for c in db.query(Candidate)}
    line("번호", "seq", "이벤트", "지역", "후보", "개표율", w=(5, 5, 10, 6, 7, 8))
    keys = {}
    for e in db.query(CountEvent).order_by(CountEvent.event_id):
        line(e.event_id, e.seq, N.get(e.event_type, e.event_type), names.get(e.region_code), cands.get(e.candidate_id, "-"),
             f"{e.payload.get('counted_rate')}%" + (f" ({e.payload['milestone']}% 구간)" if e.payload.get("milestone") else ""),
             w=(5, 5, 10, 6, 7, 8))
        if e.event_key:
            keys[e.event_key] = keys.get(e.event_key, 0) + 1
    dup = {k: v for k, v in keys.items() if v > 1}
    print(f"\n  이벤트 {db.query(CountEvent).count()}건 · 중복 열쇠 {dup or '없음'}  (시나리오 끝까지 받으면 22건)")


def article(db, aid):
    a = db.get(Article, aid)
    if not a:
        return print("그 번호의 기사가 없습니다")
    ev = db.get(CountEvent, a.event_id)
    users = {u.user_id: u.name for u in db.query(User)}
    script_len = len(a.anchor_script.replace(" ", ""))
    print(f"[기사 {a.article_id}] {a.status} · 담당 {users.get(a.reporter_id)} · 모델 {a.ai_model} · 이벤트 {N.get(a.event_type)}")
    print(f"제목: {a.title}\n본문: {a.body}\n원고: {a.anchor_script}")
    print(f"\n원고 {script_len}자 (공백 빼고) · 예상 {rules.expected_seconds(a.anchor_script):.0f}초 → 기준 120~180자: "
          f"{'통과' if 120 <= script_len <= 180 else '확인 필요'}")
    real = set(map(str, ev.payload.get("vote_rates", {}).values())) | {str(ev.payload.get("counted_rate"))}
    found = set(re.findall(r"(\d{1,3}\.\d{1,2})\s*%", a.body + a.anchor_script))
    print(f"글에 나온 득표율·개표율 {sorted(found) or '없음'} / 실제 {sorted(real)} → {'일치' if found <= real else '다름!'}")
    docs = db.query(CandidateDoc).filter(CandidateDoc.doc_id.in_(a.rag_sources or [])).all()
    print("참고 자료:", ", ".join(d.title for d in docs) or "없음")
    for r in db.query(ArticleReview).filter_by(article_id=aid).order_by(ArticleReview.review_id):
        print(f"검토: {r.created_at:%H:%M:%S} {users.get(r.desk_id)} {r.action} {r.comment or ''}")


def latency(db):
    line("기사", "승인", "음성 준비", "걸린 초", "판정", w=(5, 10, 10, 8, 6))
    for a in db.query(Article).filter(Article.approved_at.isnot(None)).order_by(Article.approved_at):
        t = db.query(TtsAudio).filter_by(article_id=a.article_id).order_by(TtsAudio.tts_id).first()
        if t:
            sec = (t.created_at - a.approved_at).total_seconds()
            line(a.article_id, f"{a.approved_at:%H:%M:%S}", f"{t.created_at:%H:%M:%S}", f"{sec:.1f}", "통과" if sec <= 15 else "느림",
                 w=(5, 10, 10, 8, 6))
        else:
            line(a.article_id, f"{a.approved_at:%H:%M:%S}", "음성 없음", "-", "키 없음·실패", w=(5, 10, 10, 8, 6))
    print("\n  기준(NFR-01): 승인 → 음성 준비 15초 이내. 웹 표시(3초)는 화면으로 확인")


def queue(db):
    line("대기", "기사", "기사상태", "이벤트", "우선", "상태", "음성 파일", w=(5, 5, 9, 9, 5, 9, 30))
    bad = 0
    for q in db.query(OnairQueue).order_by(OnairQueue.queue_id):
        a = db.get(Article, q.article_id)
        t = db.get(TtsAudio, q.tts_id) if q.tts_id else None
        exists = (config.APP_DIR / t.file_path.lstrip("/")).exists() if t else None
        if a.status != "APPROVED" or exists is False:
            bad += 1
        line(q.queue_id, a.article_id, a.status, N.get(q.event_type, q.event_type), q.priority, q.status,
             (t.file_path + (" (있음)" if exists else " (없음!)")) if t else "-", w=(5, 5, 9, 9, 5, 9, 30))
    print(f"\n  문제 {bad}건 (승인 안 된 기사이거나 음성 파일이 없는 경우)")


def llm():
    from openai import OpenAI
    if not config.OPENAI_API_KEY:
        return print(".env에 OPENAI_API_KEY가 없습니다")
    r = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30).chat.completions.create(
        model=config.LLM_MODEL, messages=[{"role": "user", "content": "한 문장으로 인사해 줘."}])
    print(f"설정 모델: {config.LLM_MODEL} · 응답 모델: {r.model}\n응답: {r.choices[0].message.content}")


def tts(text):
    from app.workers.tts_worker import synth
    if not config.OPENAI_API_KEY:
        return print(".env에 OPENAI_API_KEY가 없습니다")
    config.TTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.TTS_DIR / "check_tts.wav"
    sec = synth(text, out)
    print(f"만든 파일: {out}\n길이 {sec:.1f}초 (예상 {rules.expected_seconds(text):.1f}초) · 모델 {config.TTS_MODEL} · 목소리 {config.TTS_VOICE}")
    print("파일을 열어 이름 발음을 들어 보세요.")


def main():
    if not args:
        return print(__doc__)
    cmd = args[0]
    if cmd == "llm":
        return llm()
    if cmd == "tts":
        return tts(args[1] if len(args) > 1 else "기호 1번 윤별하, 2번 류해온, 3번 오로라 후보입니다.")
    init_db()
    with SessionLocal() as db:
        if cmd == "counts":
            counts(db)
        elif cmd == "events":
            events(db)
        elif cmd == "article":
            article(db, int(args[1]))
        elif cmd == "latency":
            latency(db)
        elif cmd == "queue":
            queue(db)
        else:
            print(__doc__)


if __name__ == "__main__":
    main()
