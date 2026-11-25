"""방송국 초기 데이터 — 계정 5개 · 후보·지역(선관위와 같음) · 후보 자료 · 프롬프트 · 큐시트 · 영상 목록

python seed.py           # 처음 한 번 (여러 번 실행해도 같은 결과, 비밀번호는 처음 한 번만 설정)
python seed.py --reset   # 수신 결과·이벤트·기사·대기열까지 지우고 다시 (리허설 전)
"""
import re
import sys
from pathlib import Path

from app import config
from app.db import SessionLocal, init_db
from app.logic.writer import DEFAULT_SYSTEM, DEFAULT_USER
from app.models import (Article, ArticleReview, AvatarVideo, Candidate, CandidateDoc, CountEvent, CueSheet, MediaAsset,
                        OnairQueue, OnairState, PromptTemplate, Region, ResultLatest, SyncLog, TtsAudio, User)
from app.security import hash_password

ACCOUNTS = [("reporter1", "기자1", "REPORTER"), ("reporter2", "기자2", "REPORTER"), ("reporter3", "기자3", "REPORTER"),
            ("desk1", "데스크1", "DESK"), ("desk2", "데스크2", "DESK")]
CANDIDATES = [(1, "윤별하", "은하공화연합", "#FF2BD6"), (2, "류해온", "심해행성연맹", "#00E5FF"), (3, "오로라", "무소속", "#A6FF00")]
REGIONS = [("ALL", "전체", 351000, 0), ("STAR", "별빛구", 82000, 1), ("DEEP", "심해구", 76000, 2), ("DUNE", "사막구", 64000, 3),
           ("NEBULA", "성운구", 71000, 4), ("ORBIT", "궤도구", 58000, 5)]
# 순서, 시작, 길이(초), 구간, 이름, 시작 조건, 후보 (01 기획서 20분 큐시트)
CUES = [(1, 0, 60, "COUNTDOWN", "개표 카운트다운 영상", "AUTO", None), (2, 60, 30, "ANCHOR", "오프닝 멘트 (AI 앵커)", "AUTO", None),
        (3, 90, 60, "INTRO", "기호 1 후보 소개 영상", "AUTO", 1), (4, 150, 60, "INTRO", "기호 2 후보 소개 영상", "AUTO", 2),
        (5, 210, 60, "INTRO", "기호 3 후보 소개 영상", "AUTO", 3), (6, 270, 660, "LIVE", "실시간 개표 보도", "AUTO", None),
        (7, 930, 60, "INTERVIEW", "당선자 인터뷰 영상", "ELECTED", None), (8, 990, 60, "PROFILE", "당선자 지난 이력·공약 영상", "AUTO", None),
        (9, 1050, 140, "LIVE", "최종 결과 정리", "AUTO", None), (10, 1190, 10, "CLOSING", "개표방송 마무리 영상", "AUTO", None)]
# 영상 파일 이름 약속 — app/static/media/ 에 이 이름으로 넣으면 송출 화면이 틉니다 (없으면 제목 화면)
MEDIA = ([("COUNTDOWN", None, "개표 카운트다운", "countdown.mp4", 60), ("OPENING", None, "오프닝 멘트 (립싱크 아바타)", "opening.mp4", 30),
          ("CLOSING", None, "개표방송 마무리", "closing.mp4", 10), ("BGM", None, "배경음악", "bgm.mp3", 120),
          ("LOOP", None, "AI 앵커 루프", "anchor_loop.mp4", 15)]
         + [(t, c, f"기호 {c} {label}", f"{t.lower()}_{c}.mp4", 60) for c in (1, 2, 3)
            for t, label in (("INTRO", "후보 소개"), ("INTERVIEW", "당선자 인터뷰"), ("PROFILE", "지난 이력·공약"))])
EVENT_HINTS = {
    "RATE_MILESTONE": "개표율 구간 돌파 기사다. 현재 순위와 격차를 중심으로, 결과를 단정하지 말고 쓴다.",
    "LEAD_CHANGE": "1위가 바뀐 기사다. 누가 누구를 제쳤는지와 격차를 먼저 쓴다.",
    "WIN_LIKELY": "당선 유력 기사다. '유력'이라는 말을 정확히 쓰고, 확정처럼 쓰지 않는다. 후보 이력 한 줄을 넣는다.",
    "WIN_SURE": "당선 확실 기사다. 방송국 판단 기준임을 밝히고, 후보 공약 한 가지를 넣는다.",
    "ELECTED": "당선 확정 기사다. 당선 소감 대신 이력과 대표 공약을 자료에서 골라 정리한다.",
}
DOC_DIR = Path(__file__).resolve().parent / "app" / "rag" / "candidate_docs"


def parse_docs():
    """candidate_docs/*.md → (후보, 종류, 제목, 본문, 출처). 파일 이름 앞 숫자 = 후보 번호."""
    out = []
    for f in sorted(DOC_DIR.glob("*.md")):
        cid = int(f.name.split("_", 1)[0])
        for m in re.finditer(r"^## (PROFILE|PLEDGE) \| (.+?)\n(.*?)(?=^## |\Z)", f.read_text(encoding="utf-8"), re.M | re.S):
            out.append((cid, m.group(1), m.group(2).strip(), m.group(3).strip(), f"rag/candidate_docs/{f.name}"))
    return out


def run(reset: bool = False, quiet: bool = False):
    init_db()
    with SessionLocal() as db:
        if reset:
            db.query(OnairState).delete()
            for t in (OnairQueue, TtsAudio, AvatarVideo, ArticleReview, Article, CountEvent, SyncLog, ResultLatest):
                db.query(t).delete()
            db.commit()
        for login, name, role in ACCOUNTS:
            u = db.query(User).filter_by(login_id=login).first()
            if not u:
                db.add(User(login_id=login, name=name, role=role, password_hash=hash_password(config.DEFAULT_PASSWORD)))
        for cid, name, party, color in CANDIDATES:
            db.merge(Candidate(candidate_id=cid, ballot_no=cid, name=name, party=party, color=color))
        for code, name, electors, order in REGIONS:
            db.merge(Region(region_code=code, name=name, electors=electors, sort_order=order))
        db.flush()
        db.query(CandidateDoc).delete()
        for i, (cid, dtype, title, content, src) in enumerate(parse_docs(), 1):
            db.add(CandidateDoc(doc_id=i, candidate_id=cid, doc_type=dtype, title=title, content=content, source=src))
        for etype, hint in EVENT_HINTS.items():
            tpl = db.query(PromptTemplate).filter_by(event_type=etype).first()
            if not tpl:                         # 학생이 고친 프롬프트는 덮어쓰지 않음
                db.add(PromptTemplate(event_type=etype, system_prompt=DEFAULT_SYSTEM + " " + hint, user_prompt=DEFAULT_USER, active=True))
        media_ids = {}
        for i, (mtype, cid, title, fname, dur) in enumerate(MEDIA, 1):
            db.merge(MediaAsset(media_id=i, media_type=mtype, candidate_id=cid, title=title, file_path=f"/static/media/{fname}", duration_sec=dur))
            media_ids[(mtype, cid)] = i
        for order, start, dur, seg, title, trig, cid in CUES:
            mid = media_ids.get(({"ANCHOR": "OPENING"}.get(seg, seg), cid))
            db.merge(CueSheet(cue_id=order, order_no=order, segment_type=seg, title=title, planned_start_sec=start, duration_sec=dur,
                              media_id=mid, trigger_type=trig, status="READY", candidate_id=cid))
        if not db.get(OnairState, 1):
            db.add(OnairState(id=1, status="STANDBY"))
        db.commit()
        from app import rag
        n = rag.build_index(db)
    if not quiet:
        print(f"초기 데이터 완료 ({config.STATION_NAME}): 계정 5 · 후보 3 · 구 5 · 후보 자료 {len(parse_docs())} · 큐시트 10"
              + (f" · 벡터 색인 {n}" if n else " · 검색은 낱말 방식(Chroma 미사용)"))
        print(f"  처음 비밀번호: .env의 DEFAULT_PASSWORD (지금 값 길이 {len(config.DEFAULT_PASSWORD)}자) — 첫 로그인 뒤 팀에서 관리")


if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
