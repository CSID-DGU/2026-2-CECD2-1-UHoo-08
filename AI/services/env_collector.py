"""지역별 실외 환경을 매시 모아 env_observations 에 넣고, 그날 env_daily 를 다시 집계한다.

생활 환경 점수(env_fit), 홈 환경 카드, BE 환경 요약이 모두 4주 누적을 읽는다.
지난 날씨는 소급해서 모을 수 없으므로 앱과 같이 뜬다(인스타 수집과 같은 방식).

── 호출 수 ───────────────────────────────────────────────────────
    기상청 초단기실황·자외선   지역마다 1회씩, 시간당 32회  (일 10,000회 제한)
    에어코리아                 전국 1회로 16개 지역을 한 번에  (일 500회 제한)

에어코리아를 지역마다 부르면 16 × 24 = 384회라 키오스크 조회와 합치면 하루 제한을
넘는다. 시·도별 조회에 sidoName=전국 을 주면 전국 측정소가 한 번에 오므로 그것을
시·도로 나눈다.

── 저장 ─────────────────────────────────────────────────────────
관측 시각은 정시로 맞춘다. (region, observed_at) 가 유일하므로 같은 시간에 몇 번을
다시 돌려도 한 줄만 남는다. 넣은 뒤에는 그 날짜를 통째로 다시 집계한다
(refresh_env_daily, 039 에서 하루 경계를 KST 로 고침).

지역 하나가 실패해도 나머지는 저장한다. 값이 하나도 없는 지역은 넣지 않는다.
못 받은 시간을 "0" 으로 남기면 4주 평균이 틀어진다.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 에어코리아 전국 측정소는 700곳이 안 된다. 한 쪽에 다 받는다.
_AIR_ROWS = 1000
_METRICS = ("temperature", "humidity", "uv_index", "pm10", "pm25")

# 수동 실행(API)과 스케줄이 겹쳐도 차례로 돈다. 둘이 같은 시간을 동시에 넣으면
# 결과는 같지만 외부 호출이 두 배가 된다.
_lock = threading.Lock()


def _weather():
    # weather 는 config(키)를 읽는다. 맨 위에서 가져오면 키 없는 CI 에서 이 모듈의
    # 순수 함수조차 시험할 수 없다.
    from services.iot import weather
    return weather


def _num(v: Any) -> float | None:
    """에어코리아 값은 문자열이고 '-' 나 빈칸이 섞여 온다."""
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ── 에어코리아 전국 조회 ─────────────────────────────────────────

def _parse_air_time(raw: Any) -> datetime | None:
    """'2026-11-27 11:00'. 자정은 '2026-11-27 24:00' 으로 오기도 한다."""
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if s.endswith("24:00"):
            day = datetime.strptime(s[:10], "%Y-%m-%d")
            return (day + timedelta(days=1)).replace(tzinfo=KST)
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return None


def group_air(items: list[dict]) -> dict[str, dict[str, Any]]:
    """전국 측정소 목록을 시·도별 중앙값으로 접는다.

    weather.fetch_air 와 같은 규칙이다. 플래그가 붙은 값(점검·장비 이상)은 뺀다.
    """
    by_sido: dict[str, dict[str, list]] = {}
    for it in items:
        sido = it.get("sidoName")
        if not sido:
            continue
        bucket = by_sido.setdefault(sido, {"pm10": [], "pm25": [], "times": []})
        if it.get("pm10Flag") is None and (v := _num(it.get("pm10Value"))) is not None:
            bucket["pm10"].append(v)
        if it.get("pm25Flag") is None and (v := _num(it.get("pm25Value"))) is not None:
            bucket["pm25"].append(v)
        if (t := _parse_air_time(it.get("dataTime"))) is not None:
            bucket["times"].append(t)

    return {
        sido: {
            "pm10": statistics.median(b["pm10"]) if b["pm10"] else None,
            "pm25": statistics.median(b["pm25"]) if b["pm25"] else None,
            "observed_at": max(b["times"]) if b["times"] else None,
            "station_n": len(b["pm25"]),
        }
        for sido, b in by_sido.items()
    }


def fetch_air_all() -> dict[str, dict[str, Any]]:
    """전국 미세먼지를 한 번에 받아 시·도별로 나눈다. 실패하면 빈 dict."""
    weather = _weather()
    key = weather._key()
    if not key:
        return {}
    try:
        with httpx.Client(timeout=weather.TIMEOUT_S * 2) as client:
            r = client.get(weather.AIRKOREA_URL, params={
                "serviceKey": key, "returnType": "json", "numOfRows": _AIR_ROWS,
                "pageNo": 1, "sidoName": "전국", "ver": "1.0",
            })
            r.raise_for_status()
            body = r.json()
    except Exception:
        logger.exception("에어코리아 전국 조회 실패")
        return {}

    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if header and str(header.get("resultCode")) not in ("00", "0"):
        logger.warning("에어코리아 전국 코드 %s %s", header.get("resultCode"), header.get("resultMsg"))
        return {}
    return group_air((resp.get("body") or {}).get("items") or [])


# ── 한 지역의 관측 한 줄 ─────────────────────────────────────────

def _hour(t: datetime | str | None) -> datetime | None:
    if t is None:
        return None
    if isinstance(t, str):
        try:
            t = datetime.fromisoformat(t)
        except ValueError:
            return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=KST)
    return t.astimezone(KST).replace(minute=0, second=0, microsecond=0)


def build_observation(
    region: str,
    kma: dict | None,
    fallback: dict | None,
    uv: dict | None,
    air: dict | None,
    now: datetime,
) -> dict[str, Any] | None:
    """조회 결과를 env_observations 한 줄로. 값이 하나도 없으면 None.

    관측 시각은 기상청 발표 시각 → 대체 기온 시각 → 미세먼지 측정 시각 → 지금 순으로
    고르고 정시로 맞춘다.
    """
    temp_src = kma or fallback or {}
    row = {
        "region": region,
        "temperature": temp_src.get("temperature"),
        "humidity": temp_src.get("humidity"),
        "uv_index": (uv or {}).get("uv_index"),
        "pm10": (air or {}).get("pm10"),
        "pm25": (air or {}).get("pm25"),
    }
    if all(row[m] is None for m in _METRICS):
        return None

    observed = (
        _hour(temp_src.get("observed_at"))
        or _hour((air or {}).get("observed_at"))
        or _hour(now)
    )
    sources = []
    if kma:
        sources.append("기상청 초단기실황")
    elif fallback:
        sources.append("Open-Meteo 기온·습도(모델값)")
    if uv:
        sources.append("기상청 생활기상지수")
    if air:
        sources.append(f"에어코리아 측정소 {air.get('station_n', 0)}곳 중앙값")

    row["observed_at"] = observed.isoformat()
    row["source"] = " · ".join(sources)
    return row


def _air_for(region: str, cfg: dict, air_by_sido: dict) -> dict | None:
    # 광주와 전남은 에어코리아에서 '전남광주' 하나로 온다. REGIONS 의 sido 값과
    # 지역 키를 둘 다 본다.
    return air_by_sido.get(cfg["sido"]) or air_by_sido.get(region)


# ── 한 번 수집 ───────────────────────────────────────────────────

def collect_once(now: datetime | None = None, *, sb: Any = None, wx: Any = None) -> dict[str, Any]:
    """16개 지역을 한 번 모아 저장하고 그날 집계를 다시 만든다.

    sb(Supabase 클라이언트), wx(weather 모듈)는 시험에서 가짜를 넣으려고 받는다.
    wx 를 넣으면 에어코리아도 wx.fetch_air_all 로 부른다.
    """
    weather = wx or _weather()
    if sb is None:
        from db.supabase_client import get_supabase
        sb = get_supabase()

    with _lock:
        now = (now or datetime.now(timezone.utc)).astimezone(KST)
        air_by_sido = wx.fetch_air_all() if wx is not None else fetch_air_all()

        rows: list[dict] = []
        skipped: list[str] = []
        for region, cfg in weather.REGIONS.items():
            try:
                kma = weather.fetch_kma_current(cfg["grid"])
                fallback = None if kma else weather.fetch_open_meteo(cfg["lat"], cfg["lon"])
                uv = weather.fetch_uv(cfg["area_no"])
            except Exception:
                logger.exception("환경 조회 실패 region=%s", region)
                kma = fallback = uv = None
            row = build_observation(region, kma, fallback, uv, _air_for(region, cfg, air_by_sido), now)
            if row is None:
                skipped.append(region)
            else:
                rows.append(row)

        if rows:
            sb.table("env_observations").upsert(rows, on_conflict="region,observed_at").execute()

        # 넣은 줄의 (지역, KST 날짜)마다 하루 집계를 다시 만든다
        days = sorted({(r["region"], datetime.fromisoformat(r["observed_at"]).date().isoformat())
                       for r in rows})
        for region, day in days:
            sb.rpc("refresh_env_daily", {"p_region": region, "p_date": day}).execute()

    result = {
        "collected_at": now.isoformat(),
        "saved": [r["region"] for r in rows],
        "skipped": skipped,
        "air_regions": len(air_by_sido),
        "refreshed_days": [f"{r} {d}" for r, d in days],
    }
    logger.info("환경 수집: 저장 %d곳, 건너뜀 %s", len(rows), skipped or "없음")
    return result


# ── 매시 스케줄 ──────────────────────────────────────────────────

def next_run(now: datetime, minute: int) -> datetime:
    """now 이후 가장 가까운 매시 minute 분 (KST)."""
    local = now.astimezone(KST)
    at = local.replace(minute=minute, second=0, microsecond=0)
    return at if at > local else at + timedelta(hours=1)


async def run_schedule() -> None:
    """앱 시작 시 한 번 돌고, 이후 매시 ENV_COLLECT_MINUTE 분에 돈다.

    시작하자마자 한 번 도는 이유: 배포로 재시작된 시간을 놓치지 않으려고.
    같은 시간을 다시 넣어도 한 줄이라 겹쳐도 괜찮다.
    """
    from config import settings

    if not settings.ENV_COLLECT_ENABLED or not settings.KMA_SERVICE_KEY:
        logger.info("환경 수집 스케줄 꺼짐 (ENV_COLLECT_ENABLED=false 또는 KMA_SERVICE_KEY 없음)")
        return
    minute = settings.ENV_COLLECT_MINUTE
    if not 0 <= minute <= 59:
        logger.error("환경 수집 스케줄을 켜지 못함: ENV_COLLECT_MINUTE=%s", minute)
        return

    while True:
        try:
            await asyncio.to_thread(collect_once)
        except Exception:
            # 한 번 실패해도 다음 시간에는 다시 돌아야 한다
            logger.exception("환경 수집 배치 실패")
        at = next_run(datetime.now(timezone.utc), minute)
        logger.info("다음 환경 수집: %s", at.isoformat())
        await asyncio.sleep((at - datetime.now(KST)).total_seconds())
