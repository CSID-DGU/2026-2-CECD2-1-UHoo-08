"""지난 며칠(기본 28일)의 지역별 시간 환경을 채운다. 한 번 손으로 돌리는 작업이다.

생활 환경 점수와 홈 환경 카드는 4주 누적을 본다. 매시 수집은 켠 날부터 쌓이므로
그 전 4주를 여기서 채운다. 이미 있는 시간은 건드리지 않는다. 실수집이 언제나 낫다.

── 출처 ─────────────────────────────────────────────────────────
    미세먼지   에어코리아 측정소별 한 달 실측값. 지역마다 측정소 3곳의 시간별 중앙값
               (매시 수집은 시·도 전체 측정소 중앙값이다. 과거는 측정소별로만 받을 수
               있어 3곳으로 줄인다. 호출 1 + 16 × 3 = 49회, 일 500회 제한 안)
               측정소 값이 없는 시간은 Open-Meteo 대기질 모델값으로 채운다
    기온·습도  Open-Meteo 과거 시간값(모델값). 기상청 ASOS 시간자료는 지금 키에
    자외선     등록돼 있지 않다

출처 컬럼은 "백필 · …" 으로 시작한다. 실수집과 구분하고, 나중에 지우거나 다시
채울 때 이것으로 고른다.
"""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
SOURCE_PREFIX = "백필"

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
AIRKOREA_SIDO = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
AIRKOREA_STATION = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"

STATIONS_PER_REGION = 3
TIMEOUT_S = 20.0
_BATCH = 500
_METRICS = ("temperature", "humidity", "uv_index", "pm10", "pm25")


def _weather():
    # REGIONS 와 키는 weather(config)에 있다. 맨 위에서 가져오면 키 없는 CI 에서
    # 이 모듈의 순수 함수조차 시험할 수 없다.
    from services.iot import weather
    return weather


def _num(v: Any) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ── 기간 ─────────────────────────────────────────────────────────

def hour_range(now: datetime, days: int) -> tuple[datetime, datetime]:
    """채울 시간 [처음, 끝]. 오늘 포함 days 일 전 0시부터 지난 정시 한 시간 전까지.

    지금 시간은 매시 수집이 넣는다.
    """
    local = now.astimezone(KST)
    start = datetime.combine(local.date() - timedelta(days=days - 1), datetime.min.time(), KST)
    end = local.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    return start, end


def _hours(start: datetime, end: datetime) -> Iterable[datetime]:
    t = start
    while t <= end:
        yield t
        t += timedelta(hours=1)


# ── 응답 읽기 ────────────────────────────────────────────────────

def parse_open_meteo(hourly: dict, fields: dict[str, str]) -> dict[datetime, dict]:
    """Open-Meteo hourly 를 {KST 정시: {우리 이름: 값}} 으로. fields 는 {응답 이름: 우리 이름}.

    timezone=Asia/Seoul 로 부르므로 시각은 시간대 없는 KST 다.
    """
    out: dict[datetime, dict] = {}
    times = hourly.get("time") or []
    for i, raw in enumerate(times):
        try:
            t = datetime.fromisoformat(raw).replace(tzinfo=KST)
        except (TypeError, ValueError):
            continue
        out[t] = {ours: _num((hourly.get(theirs) or [None] * len(times))[i])
                  for theirs, ours in fields.items()}
    return out


def _air_time(raw: Any) -> datetime | None:
    """'2026-11-27 11:00'. 자정은 '2026-11-27 24:00' 으로 오기도 한다."""
    s = str(raw or "").strip()
    try:
        if s.endswith("24:00"):
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return None


def parse_station_series(items: list[dict]) -> dict[datetime, dict]:
    """측정소 하나의 시간별 값. 플래그가 붙은 값(점검·장비 이상)은 뺀다."""
    out: dict[datetime, dict] = {}
    for it in items:
        t = _air_time(it.get("dataTime"))
        if t is None:
            continue
        out[t] = {
            "pm10": None if it.get("pm10Flag") is not None else _num(it.get("pm10Value")),
            "pm25": None if it.get("pm25Flag") is not None else _num(it.get("pm25Value")),
        }
    return out


def median_series(series: list[dict[datetime, dict]]) -> dict[datetime, dict]:
    """여러 측정소의 시간별 값을 시간마다 중앙값으로. 값이 있는 측정소만 센다."""
    out: dict[datetime, dict] = {}
    for t in {t for s in series for t in s}:
        row = {}
        for m in ("pm10", "pm25"):
            vals = [s[t][m] for s in series if t in s and s[t][m] is not None]
            row[m] = statistics.median(vals) if vals else None
        row["station_n"] = sum(1 for s in series if t in s and s[t]["pm25"] is not None)
        out[t] = row
    return out


def pick_stations(items: list[dict], region: str, sido: str, n: int = STATIONS_PER_REGION) -> list[str]:
    """전국 조회 결과에서 그 지역 측정소 n 곳. 지금 PM2.5 값이 있는 곳만 고른다.

    광주·전남은 전국 조회에서 '전남광주' 로 온다. 지역 이름과 REGIONS 의 sido 를 둘 다 본다.

    도로변 측정소(도산대로, 강남대로 …)는 뺀다. 차도 옆이라 생활 공간보다 높게 나온다.
    응답에 측정소 종류가 없어, 도로 이름으로 끝나는 이름('…로')으로 가린다.
    '송내대로(중동)' 처럼 괄호가 붙기도 하므로 괄호 앞만 본다.
    응답은 같은 구역끼리 붙어 오므로 앞에서 n 곳을 고르면 한 동네에 몰린다.
    후보를 고르게 띄워 고른다.
    """
    후보: list[str] = []
    for it in items:
        if it.get("sidoName") not in (region, sido):
            continue
        if it.get("pm25Flag") is not None or _num(it.get("pm25Value")) is None:
            continue
        name = it.get("stationName") or ""
        if name and not name.split("(")[0].endswith("로") and name not in 후보:
            후보.append(name)
    if len(후보) <= n:
        return 후보
    return [후보[i * len(후보) // n] for i in range(n)]


# ── 한 지역의 줄 만들기 ──────────────────────────────────────────

def build_rows(
    region: str,
    start: datetime,
    end: datetime,
    weather: dict[datetime, dict],
    air: dict[datetime, dict],
    air_model: dict[datetime, dict],
) -> list[dict]:
    """시간마다 env_observations 한 줄. 값이 하나도 없는 시간은 넣지 않는다."""
    rows = []
    for t in _hours(start, end):
        w = weather.get(t) or {}
        a = air.get(t) or {}
        m = air_model.get(t) or {}
        measured = a.get("pm25") is not None or a.get("pm10") is not None
        row = {
            "region": region,
            "observed_at": t.isoformat(),
            "temperature": w.get("temperature"),
            "humidity": w.get("humidity"),
            "uv_index": w.get("uv_index"),
            "pm10": a.get("pm10") if measured else m.get("pm10"),
            "pm25": a.get("pm25") if measured else m.get("pm25"),
        }
        if all(row[k] is None for k in _METRICS):
            continue
        sources = [SOURCE_PREFIX]
        if w:
            sources.append("Open-Meteo 기온·습도·자외선(모델값)")
        if measured:
            sources.append(f"에어코리아 측정소 {a.get('station_n', 0)}곳 중앙값")
        elif m:
            sources.append("Open-Meteo 미세먼지(모델값)")
        row["source"] = " · ".join(sources)
        rows.append(row)
    return rows


# ── 외부 호출 ────────────────────────────────────────────────────

def _get(client: httpx.Client, url: str, params: dict) -> dict:
    r = client.get(url, params=params)
    r.raise_for_status()
    return r.json()


def _airkorea_items(body: dict) -> list[dict]:
    resp = body.get("response") or {}
    header = resp.get("header") or {}
    if header and str(header.get("resultCode")) not in ("00", "0"):
        raise RuntimeError(f"에어코리아 코드 {header.get('resultCode')} {header.get('resultMsg')}")
    return (resp.get("body") or {}).get("items") or []


def fetch_region(client: httpx.Client, key: str, cfg: dict, stations: list[str], days: int) -> tuple[dict, dict, dict]:
    """한 지역의 (날씨, 측정소 미세먼지, 모델 미세먼지) 시간별 값."""
    where = {"latitude": cfg["lat"], "longitude": cfg["lon"], "timezone": "Asia/Seoul",
             "past_days": days, "forecast_days": 1}
    weather = parse_open_meteo(
        _get(client, OPEN_METEO_FORECAST,
             {**where, "hourly": "temperature_2m,relative_humidity_2m,uv_index"}).get("hourly") or {},
        {"temperature_2m": "temperature", "relative_humidity_2m": "humidity", "uv_index": "uv_index"},
    )
    air_model = parse_open_meteo(
        _get(client, OPEN_METEO_AIR, {**where, "hourly": "pm10,pm2_5"}).get("hourly") or {},
        {"pm10": "pm10", "pm2_5": "pm25"},
    )
    series = []
    for name in stations:
        try:
            items = _airkorea_items(_get(client, AIRKOREA_STATION, {
                "serviceKey": key, "returnType": "json", "numOfRows": 800, "pageNo": 1,
                "stationName": name, "dataTerm": "MONTH", "ver": "1.0",
            }))
            series.append(parse_station_series(items))
        except Exception:
            logger.exception("측정소 조회 실패 %s", name)
    return weather, median_series(series), air_model


# ── 실행 ─────────────────────────────────────────────────────────

def backfill(days: int = 28, *, write: bool = False, regions: list[str] | None = None,
             now: datetime | None = None, sb: Any = None) -> dict[str, Any]:
    """days 일을 채운다. write=False 면 만들 줄만 세고 저장하지 않는다."""
    wx = _weather()
    key = wx._key()
    now = (now or datetime.now(timezone.utc)).astimezone(KST)
    start, end = hour_range(now, days)
    targets = {r: c for r, c in wx.REGIONS.items() if not regions or r in regions}

    if write and sb is None:
        from db.supabase_client import get_supabase
        sb = get_supabase()

    summary: dict[str, Any] = {"start": start.isoformat(), "end": end.isoformat(),
                               "write": write, "regions": {}, "failed": []}
    with httpx.Client(timeout=TIMEOUT_S) as client:
        try:
            nationwide = _airkorea_items(_get(client, AIRKOREA_SIDO, {
                "serviceKey": key, "returnType": "json", "numOfRows": 1000, "pageNo": 1,
                "sidoName": "전국", "ver": "1.0",
            })) if key else []
        except Exception:
            logger.exception("에어코리아 측정소 목록 조회 실패. 미세먼지는 모델값만 쓴다")
            nationwide = []

        for region, cfg in targets.items():
            try:
                stations = pick_stations(nationwide, region, cfg["sido"])
                weather, air, air_model = fetch_region(client, key, cfg, stations, days)
                rows = build_rows(region, start, end, weather, air, air_model)
            except Exception:
                logger.exception("백필 실패 region=%s", region)
                summary["failed"].append(region)
                continue

            info = {"stations": stations, "rows": len(rows),
                    "measured_pm": sum(1 for r in rows if "에어코리아" in r["source"])}
            if write:
                info["inserted"] = _save(sb, region, rows, start)
            summary["regions"][region] = info
    return summary


def _save(sb: Any, region: str, rows: list[dict], start: datetime) -> int:
    """빈 시간만 넣고 그 지역의 날짜를 다시 집계한다. 넣은 줄 수를 돌려준다."""
    have = {
        datetime.fromisoformat(r["observed_at"]).astimezone(KST)
        for r in (sb.table("env_observations").select("observed_at")
                  .eq("region", region).gte("observed_at", start.isoformat())
                  .limit(5000).execute().data or [])
    }
    new = [r for r in rows if datetime.fromisoformat(r["observed_at"]) not in have]
    for i in range(0, len(new), _BATCH):
        # 사이에 매시 수집이 같은 시간을 넣었어도 덮어쓰지 않는다
        sb.table("env_observations").upsert(
            new[i:i + _BATCH], on_conflict="region,observed_at", ignore_duplicates=True,
        ).execute()

    days: set[date] = {datetime.fromisoformat(r["observed_at"]).date() for r in new}
    for d in sorted(days):
        sb.rpc("refresh_env_daily", {"p_region": region, "p_date": d.isoformat()}).execute()
    return len(new)
