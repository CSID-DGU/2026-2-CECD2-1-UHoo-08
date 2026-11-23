"""제품명 면에서 읽은 브랜드와 이름으로 상품 목록에서 후보를 고른다.

사진 모델이 읽은 글자를 상품 목록의 이름, 브랜드와 글자로 비교해 일치도를 매기고,
일치도가 높은 순으로 후보를 낸다. 최종 선택은 사용자가 한다.

    이름      한글을 자모로 풀어, 순서대로 겹치는 글자의 비율을 본다. 자모로 풀면 표기가 조금
              달라도(쥬시와 주시, 래스팅과 라스팅) 대부분이 겹친다
    브랜드    영문 표기를 견준다. 한글로 읽은 브랜드는 상품 이름 앞에 붙은 브랜드와 견준다
    일치도    브랜드를 읽었으면 브랜드와 이름을 합치고, 읽지 못했으면 이름만 본다

상품 목록의 브랜드는 영문(LANEIGE), 이름은 한글(라네즈 네오 쿠션 뮤이)이다. 포장에는 영문만
적힌 경우가 많아 모델에게 한글 표기도 함께 받는다. 모델의 답에서 읽는 키는 다섯 개다.

    brand             포장에 적힌 브랜드. 찍힌 그대로
    brand_en          브랜드의 영문 표기
    brand_ko          브랜드의 한글 표기
    product_name      포장에 적힌 제품 이름. 찍힌 그대로
    product_name_ko   제품 이름의 한글 표기

일치도가 기준보다 낮은 상품은 후보로 내지 않는다. 목록에 없는 제품을 비슷한 제품으로
억지로 맞히면 사용자가 다른 제품을 등록하게 된다.

DB, LLM 없이 받은 값만으로 판정한다.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping, NamedTuple, Sequence

# 내는 후보 수
후보_수 = 3
# 이 일치도보다 낮은 상품은 후보로 내지 않는다
최소_일치도 = 0.5
# 서로 다른 상품의 이름도 자모로 풀면 절반쯤은 겹친다. 이 값을 0 으로 보고 다시 잰다
이름_바닥 = 0.5
# 브랜드를 읽었을 때 일치도에서 브랜드가 차지하는 몫. 나머지는 이름이다
브랜드_비중 = 0.3

# 브랜드 일치 정도
_같은_브랜드 = 1.0
# 한쪽이 다른 쪽의 앞 단어일 때. VT 와 VT COSMETICS, MANYO FACTORY 와 MA:NYO
_앞_단어_일치 = 0.9
# 한두 글자만 다를 때. 로고를 잘못 읽었거나 표기가 다른 경우다
_비슷한_브랜드 = 0.8
_비슷한_브랜드_기준 = 0.85

_초성 = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_중성 = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_종성 = ("",) + tuple("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")

_괄호_안 = re.compile(r"\(.*?\)|\[.*?\]")


class Candidate(NamedTuple):
    product: Mapping[str, Any]     # 받은 상품 그대로
    confidence: float              # 일치도 0~1
    name_match: float              # 이름이 겹치는 비율 0~1. 바닥을 빼기 전의 값
    brand_match: float | None      # 브랜드 일치 0~1. 브랜드를 읽지 못했으면 None


def _다듬기(글: Any) -> str:
    """비교할 글자만 남긴다. 한글, 영문 소문자, 숫자. 띄어쓰기와 기호는 뺀다."""
    if not isinstance(글, str):
        return ""
    글 = unicodedata.normalize("NFKC", 글).lower()
    return "".join(자 for 자 in 글 if 자.isdigit() or "a" <= 자 <= "z" or "가" <= 자 <= "힣")


def _단어들(글: Any) -> list[str]:
    """띄어쓰기로 나눈 단어. 단어마다 비교할 글자만 남긴다."""
    if not isinstance(글, str):
        return []
    return [단어 for 단어 in (_다듬기(조각) for 조각 in 글.split()) if 단어]


def _자모(글: str) -> str:
    """한글을 초성, 중성, 종성으로 푼다. 다른 글자는 그대로 둔다."""
    풀린: list[str] = []
    for 자 in 글:
        if "가" <= 자 <= "힣":
            번호 = ord(자) - ord("가")
            풀린 += [_초성[번호 // 588], _중성[번호 % 588 // 28], _종성[번호 % 28]]
        else:
            풀린.append(자)
    return "".join(풀린)


def _겹치는_비율(가: str, 나: str) -> float:
    """두 글이 순서대로 겹치는 글자의 비율 0~1."""
    if not 가 or not 나:
        return 0.0
    return SequenceMatcher(None, 가, 나, autojunk=False).ratio()


def _앞_단어인가(짧은: list[str], 긴: list[str]) -> bool:
    return 0 < len(짧은) < len(긴) and 긴[:len(짧은)] == 짧은


def _영문_브랜드_일치(읽은: str, 상품_브랜드: str) -> float:
    가, 나 = _다듬기(읽은), _다듬기(상품_브랜드)
    if not 가 or not 나:
        return 0.0
    if 가 == 나:
        return _같은_브랜드
    가_단어, 나_단어 = _단어들(읽은), _단어들(상품_브랜드)
    if _앞_단어인가(가_단어, 나_단어) or _앞_단어인가(나_단어, 가_단어):
        return _앞_단어_일치
    if _겹치는_비율(가, 나) >= _비슷한_브랜드_기준:
        return _비슷한_브랜드
    return 0.0


def _브랜드_일치(읽은_브랜드들: list[str], 상품: Mapping[str, Any]) -> float:
    """읽은 브랜드와 상품의 브랜드가 맞는 정도 0~1."""
    일치 = max(
        (_영문_브랜드_일치(읽은, 상품.get("brand") or "") for 읽은 in 읽은_브랜드들),
        default=0.0,
    )
    if 일치 < _같은_브랜드:
        # 상품 목록의 브랜드는 영문이라 한글로 읽은 브랜드와는 견줄 수 없다. 이름 앞의 브랜드를 본다
        이름 = _다듬기(상품.get("name"))
        if any(len(앞) >= 2 and 이름.startswith(앞) for 앞 in map(_다듬기, 읽은_브랜드들)):
            일치 = _같은_브랜드
    return 일치


def _브랜드_떼기(글: str, 브랜드들: list[str]) -> str:
    """글이 브랜드로 시작하면 그 뒤만 남긴다. 브랜드만 있는 글은 그대로 둔다."""
    for 브랜드 in sorted(브랜드들, key=len, reverse=True):
        if len(브랜드) >= 2 and 글.startswith(브랜드) and len(글) > len(브랜드):
            return 글[len(브랜드):]
    return 글


def _비교할_이름들(이름: Any, 브랜드들: list[str]) -> set[str]:
    """이름 하나를 비교할 모양들로 바꾼다. 괄호 안의 말과 앞에 붙은 브랜드를 뺀 것도 넣는다."""
    if not isinstance(이름, str):
        return set()
    모양들 = {_다듬기(이름), _다듬기(_괄호_안.sub(" ", 이름))}
    모양들 |= {_브랜드_떼기(모양, 브랜드들) for 모양 in 모양들}
    return {_자모(모양) for 모양 in 모양들 if 모양}


def _일치도(이름: float, 브랜드: float | None) -> float:
    이름_점수 = max(0.0, (이름 - 이름_바닥) / (1 - 이름_바닥))
    if 브랜드 is None:
        return 이름_점수
    return 브랜드_비중 * 브랜드 + (1 - 브랜드_비중) * 이름_점수


def match(
    answer: Mapping[str, Any],
    products: Sequence[Mapping[str, Any]],
    *,
    limit: int = 후보_수,
) -> list[Candidate]:
    """읽은 값과 가장 잘 맞는 상품을 일치도가 높은 순으로 돌려준다.

    products    상품 목록. 상품마다 id, name, brand 를 읽는다
    limit       돌려줄 후보 수

    이름을 읽지 못했으면 후보가 없다. 브랜드만으로는 어떤 상품인지 알 수 없다.
    일치도가 같으면 덧붙은 말이 적은 이름, 그다음 id 순이다.
    """
    읽은_브랜드들 = [
        값 for 값 in (answer.get("brand"), answer.get("brand_en"), answer.get("brand_ko"))
        if _다듬기(값)
    ]
    브랜드_글자들 = [_다듬기(값) for 값 in 읽은_브랜드들]
    읽은_이름들: set[str] = set()
    for 값 in (answer.get("product_name_ko"), answer.get("product_name")):
        읽은_이름들 |= _비교할_이름들(값, 브랜드_글자들)
    if not 읽은_이름들:
        return []

    브랜드_일치들 = [
        _브랜드_일치(읽은_브랜드들, 상품) if 읽은_브랜드들 else None for 상품 in products
    ]
    # 같은 브랜드로 확인된 상품이 하나라도 있으면 그 브랜드의 상품은 모두 같은 브랜드다.
    # 한글 브랜드만 읽었을 때, 이름에 브랜드가 붙지 않은 상품도 이렇게 알아본다
    확인된_브랜드들 = {
        _다듬기(상품.get("brand")) for 상품, 일치 in zip(products, 브랜드_일치들) if 일치 == _같은_브랜드
    } - {""}

    후보들: list[Candidate] = []
    for 상품, 브랜드 in zip(products, 브랜드_일치들):
        상품_이름들 = _비교할_이름들(상품.get("name"), 브랜드_글자들)
        이름 = max(
            (_겹치는_비율(읽은, 상품_이름) for 읽은 in 읽은_이름들 for 상품_이름 in 상품_이름들),
            default=0.0,
        )
        if 브랜드 is not None and _다듬기(상품.get("brand")) in 확인된_브랜드들:
            브랜드 = _같은_브랜드
        일치도 = _일치도(이름, 브랜드)
        if 일치도 >= 최소_일치도:
            후보들.append(Candidate(상품, round(일치도, 4), round(이름, 4), 브랜드))

    후보들.sort(key=lambda 후보: (
        -후보.confidence,
        len(후보.product.get("name") or ""),
        str(후보.product.get("id") or ""),
    ))
    return 후보들[:limit]
