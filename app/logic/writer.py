"""기사 글쓰기 도우미 (FN-04-01) — 프롬프트 만들기, AI 답 읽기, AI 없이 쓰는 틀 기사.

AI(gpt-6-luna)가 실패하거나 키가 없을 때도 방송이 멈추지 않도록 틀 기사를 씁니다 (LLM_FALLBACK=template).
틀 기사도 반드시 기자 확인 → 데스크 승인을 거칩니다 (NFR-03).
"""
from __future__ import annotations

import json
import re

TYPE_KO = {"RATE_MILESTONE": "개표율 구간 돌파", "LEAD_CHANGE": "1위 변동", "WIN_LIKELY": "당선 유력",
           "WIN_SURE": "당선 확실", "ELECTED": "당선 확정"}

DEFAULT_SYSTEM = (
    "너는 방송국 선거 개표방송 기자다. 주어진 개표 수치와 후보 자료만 사용해 사실대로 쓴다. "
    "수치를 바꾸거나 추측하지 않는다. 자료에 없는 공약·이력은 쓰지 않는다. "
    "후보와 정당은 모두 가상이며, 특정 실존 인물·정당·작품을 연상시키는 표현을 쓰지 않는다. "
    "반드시 JSON 한 개로만 답한다: {\"title\": 40자 이내, \"body\": 3~5문장 웹 기사, \"anchor_script\": 120~180자 방송 원고}"
)
DEFAULT_USER = (
    "[이벤트] {event_ko}\n[지역] {region_name}\n[개표율] {counted_rate}%\n[득표]\n{vote_lines}\n"
    "[1·2위 격차] {gap}표 · [남은 표 추정] {remaining}표\n{extra}\n[후보 자료]\n{docs}\n"
    "위 정보로 기사 제목, 웹 기사 본문, AI 앵커가 읽을 방송 원고를 써라."
)


def facts(event: dict, region_names: dict, cand_names: dict) -> dict:
    p = event["payload"]
    votes = p.get("votes", {})
    rates = p.get("vote_rates", {})
    lines = [f"- 기호 {c} {cand_names.get(int(c), c)}: {int(v):,}표 ({rates.get(c, 0)}%)" for c, v in votes.items()]
    extra = ""
    if event["event_type"] == "RATE_MILESTONE":
        extra = f"[돌파 구간] {p.get('milestone')}%"
    elif event["event_type"] == "LEAD_CHANGE":
        extra = f"[이전 1위] {p.get('prev_leader_name')} → [새 1위] {p.get('leader_name')}"
    return {
        "event_type": event["event_type"], "event_ko": TYPE_KO.get(event["event_type"], event["event_type"]),
        "region_code": event["region_code"], "region_name": region_names.get(event["region_code"], event["region_code"]),
        "counted_rate": p.get("counted_rate"), "vote_lines": "\n".join(lines), "gap": f"{int(p.get('gap', 0)):,}",
        "remaining": f"{int(p.get('remaining', 0)):,}", "extra": extra,
        "leader": p.get("leader"), "leader_name": p.get("leader_name") or cand_names.get(p.get("leader"), ""),
        "milestone": p.get("milestone"), "prev_leader_name": p.get("prev_leader_name"),
        "top": [(cand_names.get(int(c), c), int(v), rates.get(c, 0)) for c, v in votes.items()],
    }


def build_messages(system_prompt: str | None, user_prompt: str | None, f: dict, docs: list[dict]) -> list[dict]:
    doc_text = "\n".join(f"({d['doc_id']}) {d['title']}: {d['content'][:400]}" for d in docs) or "(없음)"
    user = (user_prompt or DEFAULT_USER).format(**{**f, "docs": doc_text})
    return [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM}, {"role": "user", "content": user}]


def parse_reply(text: str) -> dict:
    """AI 답에서 JSON을 꺼냄. 필수 칸이 없으면 ValueError."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("JSON이 없습니다")
    d = json.loads(m.group(0))
    for k in ("title", "body", "anchor_script"):
        if not str(d.get(k, "")).strip():
            raise ValueError(f"{k} 칸이 비었습니다")
    return {k: str(d[k]).strip() for k in ("title", "body", "anchor_script")}


def numbers_match(article: dict, f: dict) -> bool:
    """본문에 나온 득표율이 실제 수치와 같은지 간단 확인 (AI가 숫자를 지어내는 것 막기)."""
    real = {f"{r}" for _, _, r in f["top"]} | {f"{f['counted_rate']}"}
    found = set(re.findall(r"(\d{1,3}\.\d{1,2})\s*%", article["body"] + article["anchor_script"]))
    return found <= real


def template_article(f: dict) -> dict:
    """AI 없이 쓰는 틀 기사 — 수치만 채움."""
    t, r, lead = f["event_type"], f["region_name"], f["leader_name"]
    top = f["top"]
    first = f"{top[0][0]} {top[0][2]}%" if top else ""
    second = f"{top[1][0]} {top[1][2]}%" if len(top) > 1 else ""
    if t == "RATE_MILESTONE":
        title = f"{r} 개표율 {f['milestone']}% 돌파… {lead} 앞서"
        body = (f"{r}의 개표율이 {f['counted_rate']}%를 기록했습니다. 현재 {first}, {second}로 {lead} 후보가 "
                f"{f['gap']}표 앞서 있습니다. 남은 표는 약 {f['remaining']}표로 추정됩니다.")
        script = f"{r} 개표율이 {f['milestone']}%를 넘었습니다. 현재 {lead} 후보가 {f['gap']}표 차이로 앞서고 있습니다. " \
                 f"{first}, {second}입니다. 남은 표는 약 {f['remaining']}표로, 아직 결과를 단정하기는 이릅니다."
    elif t == "LEAD_CHANGE":
        title = f"{r} 1위 바뀌었다… {lead}, {f['prev_leader_name']} 제쳐"
        body = (f"개표율 {f['counted_rate']}% 시점에서 {r}의 1위가 {f['prev_leader_name']} 후보에서 {lead} 후보로 바뀌었습니다. "
                f"현재 {first}, {second}이며 두 후보의 차이는 {f['gap']}표입니다.")
        script = f"{r}에서 순위가 바뀌었습니다. 개표율 {f['counted_rate']}% 현재 {lead} 후보가 {f['prev_leader_name']} 후보를 " \
                 f"{f['gap']}표 차이로 앞질렀습니다. {first}, {second}입니다. 남은 개표에서 다시 뒤집힐 수 있을지 주목됩니다."
    else:
        word = {"WIN_LIKELY": "당선 유력", "WIN_SURE": "당선 확실", "ELECTED": "당선 확정"}[t]
        title = f"{lead} 후보 {word}"
        body = (f"개표율 {f['counted_rate']}% 현재 {lead} 후보가 {first}로 {f['gap']}표 앞서며 {word}입니다. "
                f"2위는 {second}입니다. 남은 표는 약 {f['remaining']}표로 추정됩니다.")
        script = f"{lead} 후보가 {word}입니다. 개표율 {f['counted_rate']}% 현재 {first}로 2위 후보와 {f['gap']}표 차이입니다. " \
                 f"{second}입니다. 방송국 판단 기준으로 {word}을 전해 드립니다."
    return {"title": title[:100], "body": body, "anchor_script": script}
