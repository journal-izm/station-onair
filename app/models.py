"""방송국 DB 테이블 — 05 DB설계서 TBL-01 · 03 · 04 · 05 · 07."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now()


class User(Base):                            # TBL-01-01
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login_id: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(10))            # REPORTER / DESK
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Candidate(Base):                       # TBL-03-01
    __tablename__ = "candidate"
    candidate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ballot_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(20))
    party: Mapped[str | None] = mapped_column(String(30), nullable=True)
    color: Mapped[str] = mapped_column(String(7))


class Region(Base):                          # TBL-03-02
    __tablename__ = "region"
    region_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    electors: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer)


class ResultLatest(Base):                    # TBL-03-03
    __tablename__ = "result_latest"
    region_code: Mapped[str] = mapped_column(ForeignKey("region.region_code"), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate.candidate_id"), primary_key=True)
    votes: Mapped[int] = mapped_column(Integer, default=0)
    vote_rate: Mapped[float] = mapped_column(Float, default=0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    counted_rate: Mapped[float] = mapped_column(Float, default=0)
    winner_flag: Mapped[str | None] = mapped_column(String(10), nullable=True)
    updated_seq: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # 설계 외 보조 칸: 구별 원자료 (다음 수신 때 전체 다시 계산용)
    counted_votes: Mapped[int] = mapped_column(Integer, default=0)


class CountEvent(Base):                      # TBL-03-04
    __tablename__ = "count_event"
    __table_args__ = (UniqueConstraint("event_key", name="uq_event_key"),)
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20))
    region_code: Mapped[str] = mapped_column(ForeignKey("region.region_code"))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidate.candidate_id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    seq: Mapped[int] = mapped_column(Integer)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    event_key: Mapped[str | None] = mapped_column(String(40), nullable=True)   # 한 번뿐인 이벤트 중복 방지 (TC-DB-04)


class SyncLog(Base):                         # TBL-03-05
    __tablename__ = "sync_log"
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    since_seq: Mapped[int] = mapped_column(Integer)
    last_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10))             # OK / FAIL
    error_msg: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Article(Base):                         # TBL-04-01
    __tablename__ = "article"
    article_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("count_event.event_id"))
    region_code: Mapped[str] = mapped_column(ForeignKey("region.region_code"))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    anchor_script: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")   # DRAFT / SUBMITTED / REJECTED / APPROVED / WITHDRAWN(모두 삭제)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    desk_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    rag_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_model: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), default="")    # 설계 외 보조 칸 (목록·대기열 규칙용)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)       # 긴급 승인 (웹 🚨·최상단, 방송 긴급 속보)


class PromptTemplate(Base):                  # TBL-04-02
    __tablename__ = "prompt_template"
    template_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20), unique=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CandidateDoc(Base):                    # TBL-04-03
    __tablename__ = "candidate_doc"
    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate.candidate_id"))
    doc_type: Mapped[str] = mapped_column(String(10))         # PROFILE / PLEDGE
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ArticleReview(Base):                   # TBL-05-01
    __tablename__ = "article_review"
    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id"))
    desk_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(10))            # APPROVE / REJECT
    comment: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MediaAsset(Base):                      # TBL-07-03
    __tablename__ = "media_asset"
    media_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[str] = mapped_column(String(10))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidate.candidate_id"), nullable=True)
    title: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(200))
    duration_sec: Mapped[int] = mapped_column(Integer)


class CueSheet(Base):                        # TBL-07-01
    __tablename__ = "cue_sheet"
    cue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[int] = mapped_column(Integer)
    segment_type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(50))
    planned_start_sec: Mapped[int] = mapped_column(Integer)
    duration_sec: Mapped[int] = mapped_column(Integer)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_asset.media_id"), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(20), default="AUTO")
    status: Mapped[str] = mapped_column(String(10), default="READY")   # READY / ON_AIR / DONE
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 설계 외 보조 칸: 후보 소개 구간의 후보


class TtsAudio(Base):                        # TBL-07-04
    __tablename__ = "tts_audio"
    tts_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id"))
    voice: Mapped[str] = mapped_column(String(20))
    file_path: Mapped[str] = mapped_column(String(200))
    duration_sec: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AvatarVideo(Base):                     # TBL-07-06
    __tablename__ = "avatar_video"
    avatar_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id"))
    provider: Mapped[str] = mapped_column(String(20))
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="REQUESTED")   # REQUESTED / READY / FAILED / TIMEOUT
    file_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OnairQueue(Base):                      # TBL-07-02
    __tablename__ = "onair_queue"
    queue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id"), unique=True)
    tts_id: Mapped[int | None] = mapped_column(ForeignKey("tts_audio.tts_id"), nullable=True)
    avatar_id: Mapped[int | None] = mapped_column(ForeignKey("avatar_video.avatar_id"), nullable=True)
    region_code: Mapped[str] = mapped_column(ForeignKey("region.region_code"))
    priority: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(10), default="PREPARING")   # PREPARING / WAITING / HOLD(대기) / PLAYING / DONE / SKIPPED / DELETED
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    played_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), default="")       # 설계 외 보조 칸 (BR-06)


class OnairState(Base):                      # TBL-07-05
    __tablename__ = "onair_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    status: Mapped[str] = mapped_column(String(10), default="STANDBY")    # STANDBY / ON_AIR / PAUSED / ENDED
    current_cue_id: Mapped[int | None] = mapped_column(ForeignKey("cue_sheet.cue_id"), nullable=True)
    current_queue_id: Mapped[int | None] = mapped_column(ForeignKey("onair_queue.queue_id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ViewerQuestion(Base):                  # 설계 외 추가: 시청자 질문 (QR → AI 답변 초안 → 데스크 승인 → 앵커 답변)
    __tablename__ = "viewer_question"
    q_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(20), default="시청자")
    question: Mapped[str] = mapped_column(String(200))
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)        # 근거 카드 [{kind,title,ref,text,highlight}]
    grounded: Mapped[bool] = mapped_column(Boolean, default=False)          # 근거로 답했는지 (아니면 "공식 자료에서 확인되지 않습니다")
    ai_model: Mapped[str] = mapped_column(String(30), default="")
    status: Mapped[str] = mapped_column(String(10), default="NEW")          # NEW / READY / APPROVED / REJECTED / AIRED
    audio_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    audio_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    aired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
