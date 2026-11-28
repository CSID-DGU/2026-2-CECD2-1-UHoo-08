"""키워드 트렌드 배치 — 게시물 날짜는 배치 기준일과 같은 KST 로 자른다."""
from datetime import date

from services.keyword_trend_job import kst_date


def test_kst_date_moves_late_utc_to_next_day():
    assert kst_date("2026-11-26T16:00:00+00:00") == date(2026, 11, 27)


def test_kst_date_keeps_same_day():
    assert kst_date("2026-11-26T03:00:00+00:00") == date(2026, 11, 26)
    assert kst_date("2026-11-26T03:00:00Z") == date(2026, 11, 26)


def test_kst_date_treats_naive_as_utc():
    assert kst_date("2026-11-26T15:30:00") == date(2026, 11, 27)
