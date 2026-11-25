"""후보 자료 검색 (RAG) — Chroma 벡터 검색, 안 되면 낱말 검색.

- chromadb가 설치돼 있고 OPENAI_API_KEY가 있으면: vectordb/ 폴더에 색인(임베딩 EMBED_MODEL)하고 비슷한 문단을 찾음
- 아니면: logic.retrieve.keyword_search (표준 라이브러리)
색인은 원본(candidate_doc 표)에서 언제든 다시 만들 수 있으므로 Git에 올리지 않음.
"""
from __future__ import annotations

import logging

from .. import config
from ..logic.retrieve import keyword_search

log = logging.getLogger("rag")
_collection = None
_disabled = False


def _docs_dicts(db) -> list[dict]:
    from ..models import CandidateDoc
    return [{"doc_id": d.doc_id, "candidate_id": d.candidate_id, "doc_type": d.doc_type, "title": d.title,
             "content": d.content, "source": d.source} for d in db.query(CandidateDoc).all()]


def _chroma():
    """Chroma 컬렉션 (없으면 None)."""
    global _collection, _disabled
    if _collection is not None or _disabled:
        return _collection
    if not config.OPENAI_API_KEY:
        _disabled = True
        return None
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        ef = embedding_functions.OpenAIEmbeddingFunction(api_key=config.OPENAI_API_KEY, model_name=config.EMBED_MODEL)
        _collection = client.get_or_create_collection(f"candidate_docs_{config.STATION_CODE.lower()}", embedding_function=ef)
    except Exception as e:  # 설치 안 됨·키 문제 → 낱말 검색으로
        log.warning("Chroma 사용 안 함: %s", e)
        _disabled = True
    return _collection


def build_index(db) -> int:
    """candidate_doc 전체를 다시 색인 (seed.py가 부름). 색인한 문단 수."""
    col = _chroma()
    docs = _docs_dicts(db)
    if not col or not docs:
        return 0
    col.upsert(ids=[str(d["doc_id"]) for d in docs], documents=[f"{d['title']}\n{d['content']}" for d in docs],
               metadatas=[{"doc_id": d["doc_id"], "candidate_id": d["candidate_id"], "doc_type": d["doc_type"],
                           "source": d["source"] or ""} for d in docs])
    return len(docs)


def search(db, query: str, candidate_ids: list[int] | None = None, k: int = 3) -> list[dict]:
    docs = _docs_dicts(db)
    col = _chroma()
    if col:
        try:
            where = {"candidate_id": {"$in": candidate_ids}} if candidate_ids else None
            res = col.query(query_texts=[query], n_results=k, where=where)
            ids = [int(m["doc_id"]) for m in res["metadatas"][0]]
            by_id = {d["doc_id"]: d for d in docs}
            found = [by_id[i] for i in ids if i in by_id]
            if found:
                return found
        except Exception as e:
            log.warning("벡터 검색 실패, 낱말 검색으로: %s", e)
    return keyword_search(docs, query, candidate_ids, k)
