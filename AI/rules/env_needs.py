"""최근 4주 환경 집계에서 "요즘 필요한 기능"을 정한다. 입력이 같으면 결과가 같다.

생활 환경 점수와 홈 환경 카드는 하루 날씨가 아니라 4주 누적을 본다. 어제 하루 건조했다고
보습 크림을 권하지 않는다. 그래서 기능마다 "그런 날이 며칠 이상"으로 판단한다.

── 날의 기준 ─────────────────────────────────────────────────────
BE 환경 요약(application.yml 의 hwadam.env)과 같은 값을 쓴다. 화면의 "건조한 날 N일"과
카드의 이유가 다른 기준으로 세어지면 숫자가 어긋난다. 한쪽을 바꾸면 다른 쪽도 바꾼다.

    건조     습도 평균 40% 미만            (hwadam.env.humidity-low)
    자외선   최고 자외선 지수 6 이상        (hwadam.env.uv-high)
    미세먼지 PM10 평균 80 초과 또는 PM2.5 평균 35 초과 (pm10-bad, pm25-bad)
    추위     기온 평균 5도 이하             (화면 기준 없음. 겨울 보습 판단용)
    더위     최고 기온 28도 이상            (화면 기준 없음. 여름 베이스 판단용)

관측이 없는 날(sample_count = 0)은 세지 않는다. "괜찮은 날"로 세면 수집이 끊긴 기간이
좋은 날씨처럼 보인다.

── 기능 ─────────────────────────────────────────────────────────
키는 홈 환경 골든셋(eval/prompts/home_env_v1.md)과 같다. 특징 조건은 rules/env_match.py 로
보유 제품이 채우는지 판정하고, conditions 는 Retrieve 가 검색 문장에 붙인다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

HUMIDITY_LOW = 40
UV_HIGH = 6
PM10_BAD = 80
PM25_BAD = 35
COLD_TEMP = 5
HOT_TEMP_MAX = 28

# 기능을 권할 만큼 그런 날이 있었는지. 4주 중 일주일 남짓이다.
MIN_DAYS = {"dry": 7, "cold": 7, "uv": 5, "dust": 5, "hot": 7}
# 관측 일수가 이보다 적으면 판단하지 않는다. 며칠치로 4주를 말할 수 없다.
MIN_OBSERVED_DAYS = 7


def _세기(rows: list[dict]) -> dict[str, int]:
    def 값(r, k):
        return r.get(k)

    def 센다(조건) -> int:
        return sum(1 for r in rows if 조건(r))

    return {
        "dry": 센다(lambda r: 값(r, "humidity_avg") is not None and r["humidity_avg"] < HUMIDITY_LOW),
        "cold": 센다(lambda r: 값(r, "temp_avg") is not None and r["temp_avg"] <= COLD_TEMP),
        "uv": 센다(lambda r: 값(r, "uv_max") is not None and r["uv_max"] >= UV_HIGH),
        "dust": 센다(lambda r: (값(r, "pm10_avg") is not None and r["pm10_avg"] > PM10_BAD)
                    or (값(r, "pm25_avg") is not None and r["pm25_avg"] > PM25_BAD)),
        "hot": 센다(lambda r: 값(r, "temp_max") is not None and r["temp_max"] >= HOT_TEMP_MAX),
    }


def _넘었다(일수: dict[str, int], 종류: str) -> bool:
    return 일수[종류] >= MIN_DAYS[종류]


def _건조_이유(일수: dict[str, int]) -> tuple[str, str] | None:
    """보습이 필요한 이유 (근거, 배지 문구). 건조가 추위보다 직접적이라 먼저 본다."""
    if _넘었다(일수, "dry"):
        return f"습도 {HUMIDITY_LOW}% 미만 {일수['dry']}일", "요즘 공기가 건조해요"
    if _넘었다(일수, "cold"):
        return f"평균 기온 {COLD_TEMP}도 이하 {일수['cold']}일", "날이 추워 피부가 건조해지기 쉬워요"
    return None


def needs_from(일수: dict[str, int]) -> list[dict[str, Any]]:
    """일수 → 필요한 기능 목록. 순서는 화면에 보일 순서다(피부 보호 → 보습 → 진정 → 입술 → 베이스)."""
    필요들: list[dict[str, Any]] = []

    if _넘었다(일수, "uv"):
        필요들.append({
            "key": "UV_PROTECT", "label": "자외선 차단",
            "basis": f"자외선 지수 {UV_HIGH} 이상 {일수['uv']}일", "reason_text": "자외선이 강한 날이 많았어요",
            "category": "sun", "features": {}, "conditions": ["자외선 차단"],
        })

    건조 = _건조_이유(일수)
    if 건조:
        필요들.append({
            "key": "MOISTURE", "label": "보습 크림", "basis": 건조[0], "reason_text": 건조[1],
            "category": "skincare", "features": {"product_type": "크림"}, "conditions": ["보습"],
        })

    if _넘었다(일수, "dust"):
        필요들.append({
            "key": "SOOTHING", "label": "진정 토너",
            "basis": f"미세먼지 나쁨 {일수['dust']}일", "reason_text": "미세먼지 나쁜 날이 많았어요",
            "category": "skincare", "features": {"product_type": "토너"}, "conditions": ["진정"],
        })

    if 건조:
        필요들.append({
            "key": "LIP_CARE", "label": "입술 보습", "basis": 건조[0],
            "reason_text": "입술이 트기 쉬운 날씨예요",
            "category": "lip", "features": {"moisturizing": True}, "conditions": ["보습"],
        })

    if _넘었다(일수, "hot"):
        필요들.append({
            "key": "MATTE_BASE", "label": "보송한 베이스",
            "basis": f"최고 기온 {HOT_TEMP_MAX}도 이상 {일수['hot']}일", "reason_text": "요즘 덥고 습해요",
            "category": "base", "features": {"finish": "매트"}, "conditions": ["매트", "보송"],
        })

    return 필요들


def summarize(region: str | None, rows: list[dict], start: date, end: date) -> dict[str, Any]:
    """env_daily 행들(start~end) → env_summary.

    {region, period_start, period_end, day_count, stats: {날 종류: 일수}, needs: [...]}
    """
    관측 = [r for r in rows if (r.get("sample_count") or 0) > 0]
    일수 = _세기(관측)
    return {
        "region": region,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "day_count": len(관측),
        "stats": 일수,
        "needs": needs_from(일수) if len(관측) >= MIN_OBSERVED_DAYS else [],
    }
