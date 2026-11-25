"""근거(RAG) 다루기 — 표준 라이브러리만 씀 (테스트하기 쉽게).

- 공식 자료(rag/official_docs/*.md) 읽기
- 질문에 맞는 근거 찾기 + 근거가 충분한지 판단 (부족하면 "공식 자료에서 확인되지 않습니다")
- 근거 문단에서 질문·문장과 가장 겹치는 한 문장 고르기 (화면의 근거 카드에서 하이라이트)
- 기사 문장마다 어느 근거 카드를 보여 줄지 짝짓기
"""
from __future__ import annotations

import re
from pathlib import Path

from .retrieve import tokens

NOT_FOUND = "공식 자료에서 확인되지 않습니다."
MIN_SCORE = 3                       # 질문과 겹치는 낱말 점수가 이보다 낮으면 '근거 없음'
STOP = {"어떻게", "무엇", "언제", "어디", "누가", "왜", "있나요", "인가요", "되나요", "하나요", "알려", "주세요", "궁금", "한빛",
        "한빛시", "선거", "투표", "모의", "모의선", "2026"}


def parse_official(text: str, source_file: str) -> list[dict]:
    """'## 제목 | 출처' 형식의 공식 자료 → 문단 목록."""
    out = []
    for m in re.finditer(r"^## (.+?) \| (.+?)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        out.append({"title": m.group(1).strip(), "ref": m.group(2).strip(), "content": m.group(3).strip(), "file": source_file})
    return out


def load_official(folder: Path) -> list[dict]:
    docs = []
    for f in sorted(folder.glob("*.md")):
        docs.extend(parse_official(f.read_text(encoding="utf-8"), f.name))
    for i, d in enumerate(docs, 1):
        d["id"] = f"O{i}"
        d["kind"] = "OFFICIAL"
    return docs


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s*|\n+", (text or "").strip())
    return [p.strip() for p in parts if p and p.strip()]


def _q_tokens(q: str) -> set[str]:
    return {t for t in tokens(q) if t not in STOP}


def score(query: str, doc: dict) -> int:
    q = _q_tokens(query)
    title = tokens(doc.get("title", ""))
    body = tokens(doc.get("content", ""))
    return len(q & body) + 2 * len(q & title)


def best_sentence(doc_text: str, query: str) -> str:
    """문단에서 질문과 가장 많이 겹치는 문장 (하이라이트용)."""
    q = _q_tokens(query)
    sents = split_sentences(doc_text) or [doc_text]
    return max(sents, key=lambda s: (len(q & tokens(s)), -len(s)))


def find_evidence(query: str, docs: list[dict], k: int = 3, min_score: int = MIN_SCORE) -> list[dict]:
    """점수 높은 근거 k개 (min_score 미만은 버림). 각 근거에 highlight(가장 맞는 문장)를 붙여 돌려줌."""
    ranked = sorted(((score(query, d), d) for d in docs), key=lambda x: x[0], reverse=True)
    out = []
    for s, d in ranked[:k]:
        if s < min_score:
            break
        out.append({"kind": d.get("kind", "OFFICIAL"), "id": d.get("id"), "title": d["title"], "ref": d.get("ref", ""),
                    "text": d["content"], "highlight": best_sentence(d["content"], query), "score": s})
    return out


def template_answer(question: str, evidence: list[dict]) -> dict:
    """AI가 없을 때: 가장 맞는 근거 문장들로 답 (근거 밖의 말은 하지 않음)."""
    if not evidence:
        return {"answer": NOT_FOUND, "used": [], "grounded": False}
    lines = [evidence[0]["highlight"]]
    if len(evidence) > 1 and evidence[1]["highlight"] not in lines and evidence[1]["score"] >= MIN_SCORE + 1:
        lines.append(evidence[1]["highlight"])
    return {"answer": " ".join(lines), "used": list(range(1, len(lines) + 1)), "grounded": True}


def qa_messages(question: str, evidence: list[dict]) -> list[dict]:
    ctx = "\n".join(f"[{i}] {e['title']} ({e['ref']})\n{e['text']}" for i, e in enumerate(evidence, 1))
    system = ("너는 개표방송 AI 앵커의 시청자 질문 답변 담당이다. 반드시 아래 [근거] 안의 내용만으로 2~3문장, 방송 말투로 답한다. "
              "근거에 없는 내용은 절대 지어내지 않는다. 근거로 답할 수 없으면 answer를 정확히 \"" + NOT_FOUND + "\"로 한다. "
              "특정 후보를 지지·비판하거나 결과를 예측하지 않는다. "
              "JSON으로만 답한다: {\"answer\": \"...\", \"used\": [쓴 근거 번호들]}")
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"[근거]\n{ctx or '(없음)'}\n\n[시청자 질문]\n{question}"}]


def parse_qa_reply(text: str, evidence: list[dict]) -> dict:
    import json
    m = re.search(r"\{.*\}", text or "", re.S)
    data = json.loads(m.group(0)) if m else {}
    ans = str(data.get("answer", "")).strip() or NOT_FOUND
    used = [int(u) for u in data.get("used", []) if str(u).isdigit() and 1 <= int(u) <= len(evidence)]
    grounded = ans != NOT_FOUND and bool(used)
    if not grounded:
        ans, used = NOT_FOUND, []
    return {"answer": ans, "used": used, "grounded": grounded}


# ── 기사 근거 카드: 문장마다 어떤 근거를 띄울지 ──
def _numbers(s: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s or "") if len(n.replace(",", "")) >= 2}


def match_sentence(sentence: str, sources: list[dict]) -> list[int]:
    """문장과 맞는 근거 카드 번호(최대 2개). 숫자가 맞으면 공식 개표 자료, 낱말이 많이 겹치면 후보 자료."""
    nums = _numbers(sentence)
    st = tokens(sentence)
    scored = []
    for i, s in enumerate(sources):
        sc = 3 * len(nums & _numbers(s["text"])) + len(st & tokens(s["title"] + " " + s["text"]))
        if s.get("kind") == "NEC" and not (nums & _numbers(s["text"])):
            sc = 0                                                   # 개표 자료는 숫자가 맞을 때만
        if sc >= 3:
            scored.append((sc, i))
    scored.sort(reverse=True)
    return [i for _, i in scored[:2]]
