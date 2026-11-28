"""4주 환경 → 필요한 기능 판정. DB 없이 돈다."""
from datetime import date, timedelta

from rules.env_match import meets
from rules.env_needs import MIN_OBSERVED_DAYS, summarize

START, END = date(2026, 10, 31), date(2026, 11, 27)


def _날(**값):
    기본 = {"temp_avg": 12.0, "temp_max": 16.0, "humidity_avg": 60.0, "uv_max": 3.0,
          "pm10_avg": 30.0, "pm25_avg": 15.0, "sample_count": 24}
    return {**기본, **값}


def _4주(특별: dict, n: int, 나머지: dict | None = None):
    return [_날(**특별) for _ in range(n)] + [_날(**(나머지 or {})) for _ in range(28 - n)]


def _키(요약):
    return [필요["key"] for 필요 in 요약["needs"]]


def test_평범한_4주면_필요한_기능이_없다():
    요약 = summarize("서울", _4주({}, 0), START, END)
    assert 요약["day_count"] == 28 and 요약["needs"] == []
    assert 요약["period_start"] == "2026-10-31" and 요약["region"] == "서울"


def test_건조한_날이_일주일_넘으면_보습_크림과_입술_보습():
    요약 = summarize("서울", _4주({"humidity_avg": 35.0}, 9), START, END)
    assert _키(요약) == ["MOISTURE", "LIP_CARE"]
    보습 = 요약["needs"][0]
    assert 보습["basis"] == "습도 40% 미만 9일" and 보습["reason_text"] == "요즘 공기가 건조해요"
    assert 요약["stats"]["dry"] == 9


def test_건조하지_않아도_추운_날이_많으면_보습이_필요하다():
    요약 = summarize("서울", _4주({"temp_avg": 2.0}, 8), START, END)
    assert _키(요약) == ["MOISTURE", "LIP_CARE"]
    assert 요약["needs"][0]["basis"] == "평균 기온 5도 이하 8일"


def test_그런_날이_기준보다_적으면_권하지_않는다():
    assert _키(summarize("서울", _4주({"humidity_avg": 35.0}, 6), START, END)) == []
    assert _키(summarize("서울", _4주({"uv_max": 8.0}, 4), START, END)) == []


def test_자외선_미세먼지_더위():
    rows = (
        [_날(uv_max=7.0) for _ in range(5)]
        + [_날(pm25_avg=40.0) for _ in range(5)]
        + [_날(temp_max=30.0) for _ in range(7)]
        + [_날() for _ in range(11)]
    )
    assert _키(summarize("부산", rows, START, END)) == ["UV_PROTECT", "SOOTHING", "MATTE_BASE"]


def test_관측이_없는_날은_세지_않고_관측이_적으면_판단하지_않는다():
    # 관측 못 한 날(sample_count 0)을 건조하지 않은 날로 세지 않는다
    rows = [_날(humidity_avg=30.0) for _ in range(MIN_OBSERVED_DAYS - 1)] + [_날(sample_count=0) for _ in range(20)]
    요약 = summarize("서울", rows, START, END)
    assert 요약["day_count"] == MIN_OBSERVED_DAYS - 1 and 요약["needs"] == []


def test_기능마다_보유_제품_판정_규칙과_맞는다():
    """특징 조건은 rules/env_match 로 보유 제품을 판정한다. 그 규칙으로 실제 제품이 채워져야 한다."""
    rows = _4주({"humidity_avg": 30.0, "uv_max": 7.0, "pm10_avg": 90.0, "temp_max": 30.0}, 10)
    필요 = {n["key"]: n for n in summarize("서울", rows, START, END)["needs"]}
    assert set(필요) == {"UV_PROTECT", "MOISTURE", "SOOTHING", "LIP_CARE", "MATTE_BASE"}

    assert meets(필요["UV_PROTECT"], {"category": "sun", "feature_json": {"product_type": "선스틱"}})
    assert meets(필요["MOISTURE"], {"category": "skincare", "feature_json": {"product_type": "크림"}})
    assert not meets(필요["MOISTURE"], {"category": "skincare", "feature_json": {"product_type": "토너"}})
    assert meets(필요["SOOTHING"], {"category": "skincare", "feature_json": {"product_type": "토너"}})
    assert meets(필요["LIP_CARE"], {"category": "lip", "feature_json": {"moisturizing": True}})
    assert meets(필요["MATTE_BASE"], {"category": "base", "feature_json": {"finish": "매트"}})
