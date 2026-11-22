"""기한 면에서 읽은 값의 확인 규칙이 지켜야 할 성질.

틀린 날짜를 채우는 것은 비워 두는 것보다 나쁘다. 사용자가 그대로 믿고 등록한다.
확인되지 않는 값은 비우고, 왜 비웠는지 남긴다.
"""
from datetime import date

import pytest

from rules import date_reading
from rules.date_reading import DateReading, verify

오늘 = date(2026, 11, 22)


def _기한(값, 글자):
    return verify({"expiry_date": 값, "expiry_text": 글자}, 오늘)


def _제조(값, 글자):
    return verify({"mfg_date": 값, "mfg_text": 글자}, 오늘)


def _개월(값, 글자):
    return verify({"pao_months": 값, "pao_text": 글자}, 오늘)


def test_세_값을_모두_읽으면_그대로_돌려준다():
    결과 = verify({
        "expiry_date": "2028-03-30", "expiry_text": "EXP 2028.03.30",
        "mfg_date": "2026-03-31", "mfg_text": "MFG 2026.03.31",
        "pao_months": 12, "pao_text": "12M",
    }, 오늘)
    assert 결과 == DateReading(expiry_date="2028-03-30", pao_months=12, mfg_date="2026-03-31")


@pytest.mark.parametrize("답", [
    {},
    {"expiry_date": None, "mfg_date": None, "pao_months": None},
    {"expiry_date": "", "mfg_date": "null", "pao_months": "없음"},
])
def test_모델이_읽지_못한_값은_이유_없이_비어_있다(답):
    assert verify(답, 오늘) == DateReading()


# ── 형식 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("값", ["2027-03-31", "2027.03.31", "2027/3/31", "20270331", 20270331])
def test_날짜는_여러_구분자로_와도_읽는다(값):
    assert _기한(값, "EXP 2027.03.31").expiry_date == "2027-03-31"


@pytest.mark.parametrize("값", ["2027년 3월 31일", "270331", "31/03/2027", "내년 봄", ["2027-03-31"], True])
def test_날짜_모양이_아니면_버린다(값):
    결과 = _기한(값, "EXP 2027.03.31")
    assert 결과.expiry_date is None
    assert 결과.dropped == {"expiry_date": date_reading.형식_아님}


@pytest.mark.parametrize("값, 글자", [
    ("2027-02-30", "EXP 2027.02.30"),
    ("2027-13-01", "EXP 2027.13.01"),
    ("2027-03-00", "EXP 2027.03.00"),
    ("0000-03-31", "EXP 0000.03.31"),
])
def test_달력에_없는_날짜는_버린다(값, 글자):
    assert _기한(값, 글자).dropped == {"expiry_date": date_reading.없는_날짜}
    assert _제조(값.replace("2027", "2026"), 글자.replace("2027", "2026")).dropped == {
        "mfg_date": date_reading.없는_날짜,
    }


# ── 근거 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("글자", [
    "EXP 2027.03.31",
    "사용기한 2027.03.31까지",
    "2027년 3월 31일",
    "EXP20270331",
    "27.03.31",
    "270331",
    "31/03/2027",
    "31032027",
    "03/31/2027",
    "31 MAR 2027",
    "Mar. 31, 2027",
    "LOT A1234 EXP 2027 03 31",
    "ＥＸＰ ２０２７．０３．３１",
])
def test_찍힌_모양이_달라도_같은_날짜면_받는다(글자):
    결과 = _기한("2027-03-31", 글자)
    assert 결과.expiry_date == "2027-03-31"
    assert 결과.dropped == {}


@pytest.mark.parametrize("글자", [
    None,
    "",
    "EXP",
    "EXP 2027.03.13",     # 일이 다르다
    "EXP 2026.03.31",     # 연이 다르다
    "LOT 27C31",          # 날짜가 아닌 제조번호
    "LOT 27C03D31",       # 영문자 사이의 숫자를 모으면 날짜처럼 이어지는 제조번호
    "LOT27C03D31",
    "2027. 0 3. 31",      # 숫자가 끊겨 읽혔다
])
def test_읽은_글자에_그_날짜가_없으면_버린다(글자):
    결과 = _기한("2027-03-31", 글자)
    assert 결과.expiry_date is None
    assert 결과.dropped == {"expiry_date": date_reading.근거_없음}


def test_숫자_덩어리의_일부만_떼어_날짜로_맞추지_않는다():
    """제조번호 12027033199 안에 20270331 이 들어 있어도 날짜로 보지 않는다."""
    assert _기한("2027-03-31", "LOT 12027033199").dropped == {"expiry_date": date_reading.근거_없음}


def test_연월만_찍힌_글자를_월일연으로_읽지_않는다():
    """03/2027 을 03/20/27 로 쪼개면 찍혀 있지 않은 20일이 만들어진다."""
    assert _기한("2027-03-20", "EXP 03/2027").dropped == {"expiry_date": date_reading.근거_없음}


def test_근거는_칸마다_따로_본다():
    결과 = verify({
        "expiry_date": "2028-03-30", "expiry_text": "MFG 2026.03.31",
        "mfg_date": "2026-03-31", "mfg_text": "MFG 2026.03.31",
    }, 오늘)
    assert (결과.expiry_date, 결과.mfg_date) == (None, "2026-03-31")
    assert 결과.dropped == {"expiry_date": date_reading.근거_없음}


# ── 연월만 찍힌 날짜 ──────────────────────────────────────────

@pytest.mark.parametrize("값, 글자, 기대", [
    ("2027-03", "EXP 2027.03", "2027-03-31"),
    ("2027-03", "EXP 03/2027", "2027-03-31"),
    ("2027-03", "EXP MAR 2027", "2027-03-31"),
    ("2027-03", "202703", "2027-03-31"),
    ("2027-04", "2027.04 까지", "2027-04-30"),
    ("2028-02", "EXP 02/28", "2028-02-29"),
    # 모델이 마지막 날을 채워서 준 답
    ("2027-03-31", "EXP 2027.03", "2027-03-31"),
])
def test_연월만_찍힌_사용기한은_그_달_마지막_날이다(값, 글자, 기대):
    결과 = _기한(값, 글자)
    assert 결과.expiry_date == 기대
    assert 결과.dropped == {}


@pytest.mark.parametrize("값, 글자", [
    ("2027-03-15", "EXP 2027.03"),      # 찍혀 있지 않은 일을 채웠다
    ("2027-03-31", "EXP 2027.03.3"),    # 잘린 일을 모델이 마지막 날로 채웠다
])
def test_찍혀_있지_않은_일을_채운_답은_버린다(값, 글자):
    결과 = _기한(값, 글자)
    assert 결과.expiry_date is None
    assert 결과.dropped == {"expiry_date": date_reading.근거_없음}


@pytest.mark.parametrize("글자", [
    "EXP 2027.03.15",
    "EXP 2027.03.1",    # 일의 뒷자리가 잘렸다
    "032027",           # 3월 2027년인지 3월 20일 27년인지 알 수 없다
])
def test_글자에_일이_찍혀_있으면_마지막_날로_채우지_않는다(글자):
    결과 = _기한("2027-03", 글자)
    assert 결과.expiry_date is None
    assert 결과.dropped == {"expiry_date": date_reading.일_불확실}


def test_제조일은_연월만으로_채우지_않는다():
    결과 = _제조("2026-03", "MFG 2026.03")
    assert 결과.mfg_date is None
    assert 결과.dropped == {"mfg_date": date_reading.일_없는_제조일}


# ── 범위 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("글자", [
    "EXP 2025.01.31",
    "exp.20250131",
    "2025.01.31까지",
    "사용기한 2025.01.31",
    "유통기한: 25.01.31",
    "Use by 31 JAN 2025",
    "ＥＸＰ ２０２５．０１．３１",
])
def test_지난_날짜도_사용기한_표시가_있으면_받는다(글자):
    """기한이 지난 제품을 등록할 수도 있다. 지났는지는 화면이 알린다."""
    assert _기한("2025-01-31", 글자).expiry_date == "2025-01-31"


@pytest.mark.parametrize("값, 글자", [
    ("2025-01-31", "2025.01.31"),
    ("2025-01-31", "20250131 LOT A12"),
    ("2026-11-22", "20261122"),          # 오늘
    ("2026-10", "2026.10"),
])
def test_표시_없이_찍힌_지난_날짜는_사용기한으로_받지_않는다(값, 글자):
    """제조일일 수 있다. 제조일을 사용기한으로 채우면 쓰는 중인 제품이 기한 지난 제품이 된다."""
    결과 = _기한(값, 글자)
    assert 결과.expiry_date is None
    assert 결과.dropped == {"expiry_date": date_reading.표시_없는_지난_날짜}


@pytest.mark.parametrize("값, 글자, 기대", [
    ("2026-11-23", "20261123", "2026-11-23"),     # 내일
    ("2028-03-30", "20280330", "2028-03-30"),
    ("2026-11", "2026.11", "2026-11-30"),         # 이번 달 말일은 아직 오지 않았다
])
def test_표시가_없어도_오늘보다_뒤의_날짜는_사용기한이다(값, 글자, 기대):
    """제조일은 오늘보다 뒤일 수 없다."""
    assert _기한(값, 글자).expiry_date == 기대


@pytest.mark.parametrize("값, 글자", [
    ("2037-03-31", "EXP 2037.03.31"),
    ("2015-03-31", "EXP 2015.03.31"),
    ("2072-03", "EXP 2072.03"),
])
def test_오늘에서_너무_먼_사용기한은_버린다(값, 글자):
    assert _기한(값, 글자).dropped == {"expiry_date": date_reading.범위_밖}


@pytest.mark.parametrize("값", ["2036-11-30", "2016-01-01"])
def test_허용_범위의_끝은_받는다(값):
    assert _기한(값, f"EXP {값}").expiry_date == 값


def test_제조일은_오늘까지만_받는다():
    assert _제조("2026-11-22", "제조 2026.11.22").mfg_date == "2026-11-22"
    assert _제조("2026-11-23", "제조 2026.11.23").dropped == {"mfg_date": date_reading.미래_제조일}


def test_너무_오래된_제조일은_버린다():
    assert _제조("2016-11-22", "제조 2016.11.22").mfg_date == "2016-11-22"
    assert _제조("2015-12-31", "제조 2015.12.31").dropped == {"mfg_date": date_reading.범위_밖}


# ── 앞뒤 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("기한, 제조", [("2026-03-31", "2026-03-31"), ("2025-03-31", "2026-03-31")])
def test_제조일이_사용기한보다_앞이_아니면_둘_다_버린다(기한, 제조):
    결과 = verify({
        "expiry_date": 기한, "expiry_text": f"EXP {기한}",
        "mfg_date": 제조, "mfg_text": f"MFG {제조}",
        "pao_months": 12, "pao_text": "12M",
    }, 오늘)
    assert (결과.expiry_date, 결과.mfg_date) == (None, None)
    assert 결과.dropped == {
        "expiry_date": date_reading.앞뒤_어긋남,
        "mfg_date": date_reading.앞뒤_어긋남,
    }
    # 날짜와 상관없는 값은 남는다
    assert 결과.pao_months == 12


# ── 개봉 후 사용 기간 ─────────────────────────────────────────

@pytest.mark.parametrize("값, 글자", [
    (12, "12M"),
    (12, "12 M"),
    (12, "개봉 후 12개월"),
    (12, "12 months"),
    (6, "6M"),
    (24, "24M / 30ml"),
    ("12", "12M"),
    ("12M", "12M"),
    (12.0, "12M"),
])
def test_개월_수와_표시가_함께_찍혀_있으면_받는다(값, 글자):
    결과 = _개월(값, 글자)
    assert 결과.pao_months == int(str(값).rstrip("M").split(".")[0])
    assert 결과.dropped == {}


@pytest.mark.parametrize("값, 글자", [
    (12, None),
    (12, "12"),         # 개월 표시가 없다
    (12, "6M"),
    (30, "30ml"),       # 용량이다
    (12, "112M"),
    (5, "1.5M"),
])
def test_개월_표시가_붙은_그_숫자가_글자에_없으면_버린다(값, 글자):
    결과 = _개월(값, 글자)
    assert 결과.pao_months is None
    assert 결과.dropped == {"pao_months": date_reading.근거_없음}


@pytest.mark.parametrize("값", [0, -6, 61, 120])
def test_개월_수가_범위를_벗어나면_버린다(값):
    assert _개월(값, f"{값}M").dropped == {"pao_months": date_reading.개월_범위_밖}


@pytest.mark.parametrize("값", [True, 12.5, "일 년", [12], {"months": 12}])
def test_개월_수가_아니면_버린다(값):
    assert _개월(값, "12M").dropped == {"pao_months": date_reading.개월_아님}
