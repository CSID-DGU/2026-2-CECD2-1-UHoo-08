"""환경 수집의 묶기·한 줄 만들기·저장 순서. 외부 API 와 DB 없이 돈다."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.env_collector import (
    KST,
    build_observation,
    collect_once,
    group_air,
    next_run,
)

NOW = datetime(2026, 11, 27, 11, 50, tzinfo=KST)


def _station(sido, pm10, pm25, time="2026-11-27 11:00", **flags):
    return {"sidoName": sido, "pm10Value": pm10, "pm25Value": pm25, "dataTime": time, **flags}


# ── 에어코리아 전국 묶기 ─────────────────────────────────────────

def test_시도별_중앙값으로_묶는다():
    air = group_air([
        _station("서울", "30", "10"),
        _station("서울", "40", "20"),
        _station("서울", "90", "60"),
        _station("부산", "20", "8"),
    ])
    assert air["서울"]["pm10"] == 40 and air["서울"]["pm25"] == 20
    assert air["서울"]["station_n"] == 3
    assert air["부산"]["pm25"] == 8


def test_플래그가_붙거나_숫자가_아닌_값은_뺀다():
    air = group_air([
        _station("서울", "30", "10"),
        _station("서울", "999", "999", pm10Flag="점검및교정", pm25Flag="점검및교정"),
        _station("서울", "-", ""),
    ])
    assert air["서울"]["pm10"] == 30 and air["서울"]["pm25"] == 10


def test_자정_24시_표기를_다음날_0시로_읽는다():
    air = group_air([_station("서울", "30", "10", time="2026-11-27 24:00")])
    assert air["서울"]["observed_at"] == datetime(2026, 11, 28, 0, 0, tzinfo=KST)


# ── 한 지역의 한 줄 ──────────────────────────────────────────────

KMA = {"temperature": 14.8, "humidity": 79.0, "observed_at": "2026-11-27T11:00:00+09:00"}
UV = {"uv_index": 2.0}
AIR = {"pm10": 31.5, "pm25": 15.0, "observed_at": datetime(2026, 11, 27, 11, tzinfo=KST), "station_n": 9}


def test_기상청_발표_시각을_관측_시각으로_쓴다():
    row = build_observation("인천", KMA, None, UV, AIR, NOW)
    assert row["observed_at"] == "2026-11-27T11:00:00+09:00"
    assert (row["temperature"], row["humidity"], row["uv_index"], row["pm10"], row["pm25"]) == \
        (14.8, 79.0, 2.0, 31.5, 15.0)
    assert "기상청 초단기실황" in row["source"] and "측정소 9곳" in row["source"]


def test_기상청이_없으면_대체_기온을_쓰고_정시로_맞춘다():
    fallback = {"temperature": 13.0, "humidity": 70.0, "observed_at": "2026-11-27T11:45"}
    row = build_observation("인천", None, fallback, None, None, NOW)
    assert row["temperature"] == 13.0
    assert row["observed_at"] == "2026-11-27T11:00:00+09:00"
    assert "Open-Meteo" in row["source"]


def test_미세먼지만_있으면_측정_시각을_쓴다():
    row = build_observation("인천", None, None, None, AIR, NOW)
    assert row["temperature"] is None and row["pm25"] == 15.0
    assert row["observed_at"] == "2026-11-27T11:00:00+09:00"


def test_값이_하나도_없으면_넣지_않는다():
    # 못 받은 시간을 빈 줄로 넣으면 하루 관측 수(sample_count)가 부풀어 오른다
    assert build_observation("인천", None, None, None, None, NOW) is None


# ── 스케줄 ───────────────────────────────────────────────────────

def test_다음_실행은_이번_시간_아니면_다음_시간의_그_분이다():
    assert next_run(datetime(2026, 11, 27, 11, 10, tzinfo=KST), 50) == datetime(2026, 11, 27, 11, 50, tzinfo=KST)
    assert next_run(datetime(2026, 11, 27, 11, 50, tzinfo=KST), 50) == datetime(2026, 11, 27, 12, 50, tzinfo=KST)
    # 서버는 UTC 로 돈다
    utc = datetime(2026, 11, 27, 14, 55, tzinfo=timezone.utc)  # KST 23:55
    assert next_run(utc, 50) == datetime(2026, 11, 28, 0, 50, tzinfo=KST)


# ── 한 번 수집 ───────────────────────────────────────────────────

class _FakeSupabase:
    def __init__(self):
        self.upserts = []
        self.rpcs = []

    def table(self, name):
        sb = self

        class _T:
            def upsert(self, rows, on_conflict):
                sb.upserts.append((name, rows, on_conflict))
                return SimpleNamespace(execute=lambda: None)
        return _T()

    def rpc(self, fn, params):
        self.rpcs.append((fn, params))
        return SimpleNamespace(execute=lambda: None)


def _fake_weather(kma_by_grid, air):
    regions = {
        "서울": {"lat": 0, "lon": 0, "grid": (60, 127), "area_no": "1", "sido": "서울"},
        "전남광주": {"lat": 0, "lon": 0, "grid": (51, 67), "area_no": "2", "sido": "전남"},
        "제주": {"lat": 0, "lon": 0, "grid": (52, 38), "area_no": "3", "sido": "제주"},
    }
    return SimpleNamespace(
        REGIONS=regions,
        fetch_kma_current=lambda grid: kma_by_grid.get(grid),
        fetch_open_meteo=lambda lat, lon: None,
        fetch_uv=lambda area_no: UV,
        fetch_air_all=lambda: air,
    )


def test_지역마다_한_줄을_넣고_그날_집계를_다시_만든다():
    sb = _FakeSupabase()
    wx = _fake_weather({(60, 127): KMA, (51, 67): KMA}, {"서울": AIR, "전남광주": AIR})

    result = collect_once(NOW, sb=sb, wx=wx)

    [(table, rows, conflict)] = sb.upserts
    assert table == "env_observations" and conflict == "region,observed_at"
    assert [r["region"] for r in rows] == ["서울", "전남광주", "제주"]
    # 전남광주는 에어코리아에서 '전남광주' 이름으로 온다
    assert rows[1]["pm25"] == 15.0
    # 제주는 기상청이 없고 미세먼지도 없지만 자외선은 있어 넣는다
    assert rows[2]["temperature"] is None and rows[2]["uv_index"] == 2.0
    assert sb.rpcs == [
        ("refresh_env_daily", {"p_region": "서울", "p_date": "2026-11-27"}),
        ("refresh_env_daily", {"p_region": "전남광주", "p_date": "2026-11-27"}),
        ("refresh_env_daily", {"p_region": "제주", "p_date": "2026-11-27"}),
    ]
    assert result["saved"] == ["서울", "전남광주", "제주"] and result["skipped"] == []


def test_KST_자정_직후_관측은_KST_날짜로_집계한다():
    sb = _FakeSupabase()
    kma = {**KMA, "observed_at": "2026-11-28T00:00:00+09:00"}
    wx = _fake_weather({(60, 127): kma}, {})
    wx.fetch_uv = lambda area_no: None
    wx.REGIONS = {"서울": wx.REGIONS["서울"]}

    collect_once(datetime(2026, 11, 28, 0, 50, tzinfo=KST), sb=sb, wx=wx)

    assert sb.rpcs == [("refresh_env_daily", {"p_region": "서울", "p_date": "2026-11-28"})]


def test_아무것도_못_받으면_쓰지_않는다():
    sb = _FakeSupabase()
    wx = _fake_weather({}, {})
    wx.fetch_uv = lambda area_no: None

    result = collect_once(NOW, sb=sb, wx=wx)

    assert sb.upserts == [] and sb.rpcs == []
    assert result["skipped"] == ["서울", "전남광주", "제주"]
