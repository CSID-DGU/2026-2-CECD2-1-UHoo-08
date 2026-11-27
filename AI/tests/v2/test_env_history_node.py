"""EnvHistory 노드. env_daily 읽기를 바꿔 끼워 DB 없이 돈다."""
from datetime import date

import pytest

from graph.nodes import env_history as 노드


@pytest.mark.asyncio
async def test_지역이_없으면_DB를_부르지_않고_빈_요약이다(monkeypatch):
    def 터짐(*a):
        raise AssertionError("지역이 없는데 DB 를 불렀다")
    monkeypatch.setattr(노드, "_rows", 터짐)

    요약 = (await 노드.env_history({"user_profile": {}}))["env_summary"]
    assert 요약["region"] is None and 요약["needs"] == [] and 요약["day_count"] == 0


@pytest.mark.asyncio
async def test_사용자_지역의_28일을_읽어_필요한_기능을_낸다(monkeypatch):
    받은 = {}

    def rows(region, start, end):
        받은.update(region=region, days=(end - start).days + 1)
        return [{"temp_avg": 1.0, "temp_max": 5.0, "humidity_avg": 70.0, "uv_max": 2.0,
                 "pm10_avg": 20.0, "pm25_avg": 10.0, "sample_count": 24} for _ in range(28)]
    monkeypatch.setattr(노드, "_rows", rows)

    요약 = (await 노드.env_history({"user_profile": {"region": "서울"}}))["env_summary"]
    assert 받은 == {"region": "서울", "days": 28}
    assert [n["key"] for n in 요약["needs"]] == ["MOISTURE", "LIP_CARE"]


def test_기간은_오늘을_포함한_28일이다():
    assert 노드.period(date(2026, 11, 27)) == (date(2026, 10, 31), date(2026, 11, 27))
