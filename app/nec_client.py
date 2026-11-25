"""선관위 API-02-01 · API-02-02 호출 (두 저장소의 약속)."""
import httpx

from . import config


class NecError(Exception):
    pass


async def _get(path: str, params: dict | None = None) -> dict:
    if not config.NEC_API_KEY:
        raise NecError(".env에 NEC_API_KEY가 없습니다")
    try:
        async with httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get(f"{config.NEC_BASE_URL}{path}", params=params, headers={"X-API-KEY": config.NEC_API_KEY})
    except httpx.HTTPError as e:
        raise NecError(f"선관위 서버 연결 실패: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise NecError(f"선관위 응답 {r.status_code}: {r.text[:120]}")
    return r.json()


async def election_info() -> dict:
    return await _get(f"/nec/v1/elections/{config.ELECTION_ID}")


async def results(since_seq: int) -> dict:
    return await _get(f"/nec/v1/elections/{config.ELECTION_ID}/results", {"since_seq": since_seq})
