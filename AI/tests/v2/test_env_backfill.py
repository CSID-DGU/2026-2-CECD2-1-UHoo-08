"""환경 백필의 기간·응답 읽기·줄 만들기·저장. 외부 API 와 DB 없이 돈다."""
from datetime import datetime
from types import SimpleNamespace

from services.env_backfill import (
    KST,
    _save,
    build_rows,
    hour_range,
    median_series,
    parse_open_meteo,
    parse_station_series,
    pick_stations,
)


def _t(day, hour):
    return datetime(2026, 11, day, hour, tzinfo=KST)


# ── 기간 ─────────────────────────────────────────────────────────

def test_오늘_포함_며칠_전_0시부터_지난_시간까지다():
    start, end = hour_range(datetime(2026, 11, 27, 11, 50, tzinfo=KST), 28)
    assert start == datetime(2026, 10, 31, 0, tzinfo=KST)
    # 11시는 매시 수집이 넣는다
    assert end == _t(27, 10)


# ── 응답 읽기 ────────────────────────────────────────────────────

def test_Open_Meteo_시각을_KST로_읽고_이름을_바꾼다():
    hourly = {"time": ["2026-11-27T00:00", "2026-11-27T01:00"],
              "temperature_2m": [3.5, None], "relative_humidity_2m": [80, 81]}
    out = parse_open_meteo(hourly, {"temperature_2m": "temperature", "relative_humidity_2m": "humidity"})
    assert out[_t(27, 0)] == {"temperature": 3.5, "humidity": 80.0}
    assert out[_t(27, 1)]["temperature"] is None


def test_측정소_값은_플래그와_빈칸을_빼고_자정_24시를_다음날로_읽는다():
    out = parse_station_series([
        {"dataTime": "2026-11-26 24:00", "pm10Value": "30", "pm25Value": "12"},
        {"dataTime": "2026-11-27 01:00", "pm10Value": "-", "pm25Value": "9", "pm10Flag": None},
        {"dataTime": "2026-11-27 02:00", "pm10Value": "999", "pm25Value": "999",
         "pm10Flag": "통신장애", "pm25Flag": "통신장애"},
    ])
    assert out[_t(27, 0)] == {"pm10": 30.0, "pm25": 12.0}
    assert out[_t(27, 1)] == {"pm10": None, "pm25": 9.0}
    assert out[_t(27, 2)] == {"pm10": None, "pm25": None}


def test_측정소_여럿을_시간마다_중앙값으로_묶는다():
    a = {_t(27, 0): {"pm10": 10, "pm25": 5}}
    b = {_t(27, 0): {"pm10": 30, "pm25": None}}
    c = {_t(27, 0): {"pm10": 20, "pm25": 7}}
    out = median_series([a, b, c])
    assert out[_t(27, 0)] == {"pm10": 20, "pm25": 6.0, "station_n": 2}


def test_지역_측정소는_값이_있는_곳만_고르게_띄워_고른다():
    items = [
        {"sidoName": "서울", "stationName": "중구", "pm25Value": "10"},
        {"sidoName": "서울", "stationName": "종로구", "pm25Value": "-"},
        {"sidoName": "부산", "stationName": "광복동", "pm25Value": "8"},
        {"sidoName": "서울", "stationName": "용산구", "pm25Value": "11", "pm25Flag": "점검및교정"},
        {"sidoName": "서울", "stationName": "광진구", "pm25Value": "12"},
        {"sidoName": "서울", "stationName": "성동구", "pm25Value": "13"},
        {"sidoName": "서울", "stationName": "강남구", "pm25Value": "14"},
        {"sidoName": "서울", "stationName": "서초구", "pm25Value": "14"},
        {"sidoName": "서울", "stationName": "송파구", "pm25Value": "14"},
    ]
    # 후보 6곳(중구 광진구 성동구 강남구 서초구 송파구)에서 0, 2, 4 번째
    assert pick_stations(items, "서울", "서울") == ["중구", "성동구", "서초구"]


def test_도로변_측정소는_고르지_않는다():
    items = [
        {"sidoName": "서울", "stationName": "도산대로", "pm25Value": "30"},
        {"sidoName": "서울", "stationName": "강남대로", "pm25Value": "30"},
        {"sidoName": "서울", "stationName": "송내대로(중동)", "pm25Value": "30"},
        {"sidoName": "서울", "stationName": "부곡동(울산)", "pm25Value": "14"},
    ]
    assert pick_stations(items, "서울", "서울") == ["부곡동(울산)"]


def test_광주_전남은_전국_조회의_전남광주_이름으로도_찾는다():
    items = [{"sidoName": "전남광주", "stationName": "농성동", "pm25Value": "10"}]
    assert pick_stations(items, "전남광주", "전남") == ["농성동"]


# ── 줄 만들기 ────────────────────────────────────────────────────

W = {_t(27, 0): {"temperature": 3.0, "humidity": 80.0, "uv_index": 0.0},
     _t(27, 1): {"temperature": 2.5, "humidity": 82.0, "uv_index": 0.0}}


def test_측정소_실측이_있으면_쓰고_없으면_모델값을_쓴다():
    air = {_t(27, 0): {"pm10": 30, "pm25": 12, "station_n": 3}}
    model = {_t(27, 0): {"pm10": 99, "pm25": 99}, _t(27, 1): {"pm10": 40, "pm25": 20}}
    rows = build_rows("서울", _t(27, 0), _t(27, 1), W, air, model)
    assert [(r["pm10"], r["pm25"]) for r in rows] == [(30, 12), (40, 20)]
    assert rows[0]["source"].startswith("백필") and "측정소 3곳" in rows[0]["source"]
    assert "Open-Meteo 미세먼지" in rows[1]["source"]
    assert rows[0]["observed_at"] == "2026-11-27T00:00:00+09:00"


def test_값이_하나도_없는_시간은_넣지_않는다():
    rows = build_rows("서울", _t(27, 0), _t(27, 2), W, {}, {})
    assert [r["observed_at"][11:13] for r in rows] == ["00", "01"]


# ── 저장 ─────────────────────────────────────────────────────────

class _FakeSupabase:
    def __init__(self, existing):
        self.existing = existing
        self.upserts = []
        self.rpcs = []

    def table(self, name):
        sb = self

        class _Q:
            def select(self, *_): return self
            def eq(self, *_): return self
            def gte(self, *_): return self
            def limit(self, *_): return self
            def execute(self): return SimpleNamespace(data=[{"observed_at": t} for t in sb.existing])

            def upsert(self, rows, on_conflict, ignore_duplicates):
                sb.upserts.append((rows, on_conflict, ignore_duplicates))
                return SimpleNamespace(execute=lambda: None)
        return _Q()

    def rpc(self, fn, params):
        self.rpcs.append(params)
        return SimpleNamespace(execute=lambda: None)


def test_이미_있는_시간은_넣지_않고_덮어쓰지도_않는다():
    rows = build_rows("서울", _t(26, 23), _t(27, 1), {**W, _t(26, 23): W[_t(27, 0)]}, {}, {})
    # 실수집이 27일 0시를 이미 넣었다 (DB 는 UTC 로 돌려준다)
    sb = _FakeSupabase(existing=["2026-11-26T15:00:00+00:00"])

    n = _save(sb, "서울", rows, _t(26, 23))

    assert n == 2
    [(saved, conflict, ignore)] = sb.upserts
    assert [r["observed_at"][8:13] for r in saved] == ["26T23", "27T01"]
    assert conflict == "region,observed_at" and ignore is True
    # 넣은 줄의 KST 날짜마다 다시 집계한다
    assert sb.rpcs == [{"p_region": "서울", "p_date": "2026-11-26"},
                       {"p_region": "서울", "p_date": "2026-11-27"}]
