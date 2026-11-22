"""기한 면 사진에서 읽은 값을 확인한다.

사진 모델은 사용기한, 제조일, 개봉 후 사용 기간을 읽어 값과 함께 그 값을 읽은 글자를
돌려준다. 그 값을 그대로 쓰지 않고 여기서 확인한 뒤, 확인되지 않는 값은 비운다.
틀린 날짜를 채우면 사용자가 그대로 믿고 등록하므로 비워 두는 편이 낫다.

    형식    달력에 있는 날짜인가. 사용기한은 연월만 찍힌 것도 받아 그 달 마지막 날로 둔다
    근거    값의 숫자가 읽은 글자에 실제로 있는가
    범위    오늘에서 너무 멀지 않은가. 제조일은 오늘보다 뒤일 수 없다
    표시    지난 날짜를 사용기한으로 받으려면 사용기한이라는 표시가 함께 찍혀 있어야 한다.
            표시 없이 찍힌 지난 날짜는 제조일일 수 있다
    앞뒤    제조일이 사용기한보다 앞인가. 아니면 어느 쪽이 틀렸는지 몰라 둘 다 비운다
    순서    03/04/2027 처럼 일과 월을 바꿔 읽어도 맞는 글자면 어느 날짜인지 몰라 비운다

모델의 답에서 읽는 키는 여섯 개다.

    expiry_date   사용기한. YYYY-MM-DD, 일이 찍혀 있지 않으면 YYYY-MM
    expiry_text   사용기한을 읽은 글자. 찍힌 그대로
    mfg_date      제조일. YYYY-MM-DD
    mfg_text      제조일을 읽은 글자
    pao_months    개봉 후 사용 기간. 개월 수
    pao_text      개봉 후 사용 기간을 읽은 글자

DB, LLM 없이 받은 값만으로 판정한다. 버린 값은 이유와 함께 돌려준다.
"""
from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable, Mapping

# 오늘에서 이 햇수보다 멀면 잘못 읽은 것으로 본다
허용_연수 = 10
# 개봉 후 사용 기간으로 받는 가장 긴 개월 수
최대_개월 = 60

# 값을 버린 이유
형식_아님 = "날짜 형식이 아니다"
없는_날짜 = "달력에 없는 날짜다"
근거_없음 = "읽은 글자에 그 값이 없다"
일_불확실 = "글자에는 일이 찍혀 있는데 값에는 없다"
일월_모호 = "글자만으로는 일과 월 중 어느 쪽인지 알 수 없다"
일_없는_제조일 = "제조일에 일이 없다"
범위_밖 = "오늘과 너무 멀다"
미래_제조일 = "제조일이 오늘보다 뒤다"
표시_없는_지난_날짜 = "지난 날짜인데 사용기한이라는 표시가 없다"
앞뒤_어긋남 = "제조일이 사용기한보다 뒤거나 같다"
개월_아님 = "개월 수가 아니다"
개월_범위_밖 = "개월 수가 범위를 벗어난다"

# 모델이 값이 없다는 뜻으로 적는 말
_없다는_말 = frozenset({"", "null", "none", "없음", "n/a", "unknown", "-"})

_날짜_모양 = re.compile(r"^(\d{4})\s*[-./]\s*(\d{1,2})(?:\s*[-./]\s*(\d{1,2}))?$")
_붙은_날짜 = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
# 날짜가 사용기한임을 알려 주는 표시. EXP, 사용기한, 유통기한, 2027.03.31까지, USE BY 등
_기한_표시 = re.compile(r"exp|기한|까지|use\s*by|best\s*before", re.IGNORECASE)
_개월_모양 = re.compile(r"^(\d{1,3})\s*(?:개월|months?|m)?$", re.IGNORECASE)
# 12M, 12 M, 12개월 처럼 숫자 바로 뒤에 개월 표시가 붙은 글자. 30ml 의 30 은 잡지 않는다
_개월_표시 = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:개월|months?|mois|mo|m)(?![a-z])", re.IGNORECASE)

_달_번호 = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_달_이름 = re.compile(
    r"(?<![a-z])(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?![a-z])",
    re.IGNORECASE,
)

# 영문자와 숫자가 붙은 덩어리. 그 밖의 글자(공백, 문장부호, 한글)는 덩어리를 나눈다
_영숫자_덩어리 = re.compile(r"[0-9a-z]+", re.IGNORECASE)
# 숫자 앞에 붙여 찍는 날짜 표시. EXP20270331, MFG20260331
_붙인_표시 = re.compile(r"^(?:exp(?:iry)?|mfg|mfd|bbe?)(\d+)$", re.IGNORECASE)

_조각_검사 = Callable[[str], bool]


@dataclass(frozen=True)
class DateReading:
    """확인을 통과한 값. 통과하지 못했거나 모델이 읽지 못한 값은 None 이다."""

    expiry_date: str | None = None   # YYYY-MM-DD
    pao_months: int | None = None
    mfg_date: str | None = None      # YYYY-MM-DD
    # 모델이 값을 줬지만 버린 것. 키는 expiry_date, mfg_date, pao_months, 값은 이유
    dropped: dict[str, str] = field(default_factory=dict)


def _없는_값(값: Any) -> bool:
    return 값 is None or (isinstance(값, str) and 값.strip().lower() in _없다는_말)


def _날짜_읽기(값: Any) -> tuple[int, int, int | None] | None:
    """모델이 준 날짜 값을 연, 월, 일로 나눈다. 연월만 있으면 일은 None. 모양이 다르면 None."""
    if isinstance(값, bool) or not isinstance(값, (str, int)):
        return None
    글 = str(값).strip()
    맞음 = _날짜_모양.match(글) or _붙은_날짜.match(글)
    if 맞음 is None:
        return None
    연, 월, 일 = 맞음.groups()
    return int(연), int(월), int(일) if 일 is not None else None


def _달력_날짜(연: int, 월: int, 일: int) -> date | None:
    try:
        return date(연, 월, 일)
    except ValueError:
        return None


def _다듬은_글(글자: Any) -> str:
    """읽은 글자. 전각 숫자와 글자를 보통 글자로 바꾼다. 글이 아니면 빈 문자열."""
    return unicodedata.normalize("NFKC", 글자) if isinstance(글자, str) else ""


def _숫자_덩어리(글자: Any) -> list[str]:
    """읽은 글자에서 숫자 덩어리만 차례로 꺼낸다. 영문 달 이름은 숫자로 바꾼다.

    영문자와 숫자가 섞인 덩어리(27C03D31 같은 제조번호)는 숫자를 꺼내지 않는다. 글자를
    빼고 숫자만 모으면 27, 03, 31 이 날짜처럼 이어진다. 날짜 표시를 앞에 붙여 찍은
    EXP20270331 만 표시를 떼고 숫자를 쓴다.
    """
    글 = _달_이름.sub(lambda 맞음: f" {_달_번호[맞음.group(1)[:3].lower()]:02d} ", _다듬은_글(글자))
    덩어리들: list[str] = []
    for 덩어리 in _영숫자_덩어리.findall(글):
        if 덩어리.isdigit():
            덩어리들.append(덩어리)
        elif 맞음 := _붙인_표시.match(덩어리):
            덩어리들.append(맞음.group(1))
    return 덩어리들


def _나누는_방법(덩어리: str) -> list[tuple[str, ...]]:
    """숫자 한 덩어리를 날짜 조각으로 읽는 방법들. 붙여 찍은 날짜(20270331)를 나눈다.

    네 자리 덩어리는 나누지 않는다. 나누면 03/2027 을 03/20/27 로도 읽게 된다.
    """
    방법: list[tuple[str, ...]] = [(덩어리,)]
    if len(덩어리) == 8:
        방법 += [(덩어리[:4], 덩어리[4:6], 덩어리[6:]), (덩어리[:2], 덩어리[2:4], 덩어리[4:])]
    elif len(덩어리) == 6:
        방법 += [
            (덩어리[:2], 덩어리[2:4], 덩어리[4:]),
            (덩어리[:4], 덩어리[4:]),
            (덩어리[:2], 덩어리[2:]),
        ]
    return 방법


def _연(연: int) -> _조각_검사:
    return lambda 조각: 조각 in (f"{연:04d}", f"{연 % 100:02d}")


def _수(값: int) -> _조각_검사:
    return lambda 조각: len(조각) <= 2 and int(조각) == 값


def _아무_일(조각: str) -> bool:
    return len(조각) <= 2 and 1 <= int(조각) <= 31


def _온_날짜_순서(연: int, 월: int, 일: _조각_검사) -> list[tuple[_조각_검사, ...]]:
    """연월일이 찍히는 순서. 연월일, 일월연, 월일연."""
    return [(_연(연), _수(월), 일), (일, _수(월), _연(연)), (_수(월), 일, _연(연))]


def _연월_순서(연: int, 월: int) -> list[tuple[_조각_검사, ...]]:
    return [(_연(연), _수(월)), (_수(월), _연(연))]


def _찍혀_있나(덩어리들: list[str], 순서들: Iterable[tuple[_조각_검사, ...]]) -> bool:
    """덩어리들 어딘가에 그 순서로 이어진 조각이 있는가.

    덩어리는 통째로만 쓴다. 덩어리의 일부만 떼어 맞추면 날짜가 아닌 숫자(제조번호 등)에서도
    날짜가 만들어진다.
    """
    def 이어서(위치: int, 남은: tuple[_조각_검사, ...]) -> bool:
        if not 남은:
            return True
        if 위치 >= len(덩어리들):
            return False
        for 조각들 in _나누는_방법(덩어리들[위치]):
            if len(조각들) > len(남은):
                continue
            if all(맞나(조각) for 맞나, 조각 in zip(남은, 조각들)) and 이어서(위치 + 1, 남은[len(조각들):]):
                return True
        return False

    return any(이어서(시작, 순서) for 순서 in 순서들 for 시작 in range(len(덩어리들)))


def _일월_바꿔도_맞나(덩어리들: list[str], 연: int, 월: int, 일: int) -> bool:
    """일과 월을 바꾼 다른 날짜도 읽은 글자에 찍혀 있는가.

    03/04/2027 은 3월 4일로도 4월 3일로도 읽힌다. 하나라도 맞으면 받으면, 모델이 고른
    쪽이 틀려도 걸러지지 않는다. 일이 12보다 크거나 일과 월이 같으면 바꿔 읽을 수 없다.
    """
    if 일 == 월 or _달력_날짜(연, 일, 월) is None:
        return False
    return _찍혀_있나(덩어리들, _온_날짜_순서(연, 일, _수(월)))


def _사용기한(값: Any, 글자: Any, today: date) -> tuple[date | None, str | None]:
    """확인한 사용기한과 버린 이유. 모델이 값을 주지 않았으면 둘 다 None."""
    if _없는_값(값):
        return None, None
    읽은 = _날짜_읽기(값)
    if 읽은 is None:
        return None, 형식_아님
    연, 월, 일 = 읽은
    if _달력_날짜(연, 월, 1 if 일 is None else 일) is None:
        return None, 없는_날짜
    if abs(연 - today.year) > 허용_연수:
        return None, 범위_밖

    덩어리들 = _숫자_덩어리(글자)
    마지막_날 = monthrange(연, 월)[1]
    if 일 is not None and _찍혀_있나(덩어리들, _온_날짜_순서(연, 월, _수(일))):
        if _일월_바꿔도_맞나(덩어리들, 연, 월, 일):
            return None, 일월_모호
        날짜 = date(연, 월, 일)
    elif 일 in (None, 마지막_날) and _찍혀_있나(덩어리들, _연월_순서(연, 월)):
        # 연월만 찍힌 사용기한은 그 달 마지막 날까지다. 모델이 마지막 날을 채워서 준 답도 받는다
        if _찍혀_있나(덩어리들, _온_날짜_순서(연, 월, _아무_일)):
            return None, 일_불확실 if 일 is None else 근거_없음
        날짜 = date(연, 월, 마지막_날)
    else:
        return None, 근거_없음
    if 날짜 <= today and not _기한_표시.search(_다듬은_글(글자)):
        return None, 표시_없는_지난_날짜
    return 날짜, None


def _제조일(값: Any, 글자: Any, today: date) -> tuple[date | None, str | None]:
    """확인한 제조일과 버린 이유. 모델이 값을 주지 않았으면 둘 다 None."""
    if _없는_값(값):
        return None, None
    읽은 = _날짜_읽기(값)
    if 읽은 is None:
        return None, 형식_아님
    연, 월, 일 = 읽은
    if 일 is None:
        return None, 일_없는_제조일
    날짜 = _달력_날짜(연, 월, 일)
    if 날짜 is None:
        return None, 없는_날짜
    if 날짜 > today:
        return None, 미래_제조일
    if today.year - 연 > 허용_연수:
        return None, 범위_밖
    덩어리들 = _숫자_덩어리(글자)
    if not _찍혀_있나(덩어리들, _온_날짜_순서(연, 월, _수(일))):
        return None, 근거_없음
    if _일월_바꿔도_맞나(덩어리들, 연, 월, 일):
        return None, 일월_모호
    return 날짜, None


def _개월_수(값: Any) -> int | None:
    if isinstance(값, bool):
        return None
    if isinstance(값, int):
        return 값
    if isinstance(값, float) and 값.is_integer():
        return int(값)
    if isinstance(값, str):
        맞음 = _개월_모양.match(값.strip())
        return int(맞음.group(1)) if 맞음 else None
    return None


def _개월(값: Any, 글자: Any) -> tuple[int | None, str | None]:
    """확인한 개봉 후 사용 기간과 버린 이유. 모델이 값을 주지 않았으면 둘 다 None."""
    if _없는_값(값):
        return None, None
    개월 = _개월_수(값)
    if 개월 is None:
        return None, 개월_아님
    if not 1 <= 개월 <= 최대_개월:
        return None, 개월_범위_밖
    if not any(int(맞음.group(1)) == 개월 for 맞음 in _개월_표시.finditer(_다듬은_글(글자))):
        return None, 근거_없음
    return 개월, None


def verify(answer: Mapping[str, Any], today: date) -> DateReading:
    """모델의 답에서 확인을 통과한 값만 남긴다.

    today 는 사용자가 있는 곳의 오늘이다. 제조일이 오늘보다 뒤인지, 날짜가 오늘에서
    너무 멀지 않은지를 이 값으로 본다.
    """
    버린: dict[str, str] = {}

    기한, 이유 = _사용기한(answer.get("expiry_date"), answer.get("expiry_text"), today)
    if 이유:
        버린["expiry_date"] = 이유
    제조, 이유 = _제조일(answer.get("mfg_date"), answer.get("mfg_text"), today)
    if 이유:
        버린["mfg_date"] = 이유
    개월, 이유 = _개월(answer.get("pao_months"), answer.get("pao_text"))
    if 이유:
        버린["pao_months"] = 이유

    if 기한 is not None and 제조 is not None and 제조 >= 기한:
        기한 = 제조 = None
        버린["expiry_date"] = 버린["mfg_date"] = 앞뒤_어긋남

    return DateReading(
        expiry_date=기한.isoformat() if 기한 else None,
        pao_months=개월,
        mfg_date=제조.isoformat() if 제조 else None,
        dropped=버린,
    )
