"""후보 자료 검색 (RAG의 R) — 기본은 낱말 겹침 점수. Chroma가 설치돼 있고 OpenAI 키가 있으면 벡터 검색(app/rag)."""
from __future__ import annotations

import re


def tokens(text: str) -> set[str]:
    """한글·영문·숫자 낱말(2글자 이상). 조사가 붙어도 앞 2~3글자로 겹치게 자름."""
    out = set()
    for w in re.findall(r"[0-9A-Za-z가-힣]+", text or ""):
        if len(w) >= 2:
            out.add(w)
            out.add(w[:2])
            if len(w) >= 3:
                out.add(w[:3])
    return out


def keyword_search(docs: list[dict], query: str, candidate_ids: list[int] | None = None, k: int = 3) -> list[dict]:
    """docs: [{"doc_id", "candidate_id", "doc_type", "title", "content"}]. 지정 후보 자료를 우선, 점수 높은 순."""
    q = tokens(query)
    scored = []
    for d in docs:
        if candidate_ids and d["candidate_id"] not in candidate_ids:
            continue
        t = tokens(d["title"] + " " + d["content"])
        score = len(q & t) + (2 if candidate_ids and d["candidate_id"] == candidate_ids[0] else 0)
        scored.append((score, -d["doc_id"], d))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [d for _, _, d in scored[:k]]
