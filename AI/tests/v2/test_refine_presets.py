"""조건 수정 선택지 표가 지켜야 할 성질.

BE 가 보내는 키, 문장과 어긋나면 선택지가 조건에 반영되지 않는다.
"""
import re
from pathlib import Path

import pytest

from contracts.query_spec import QuerySpec
from rules import refine_presets as 표

_BE_선택지 = (
    Path(__file__).resolve().parents[3]
    / "BE/src/main/java/com/capstone/backend/domain/recommendation/enums/RefinePreset.java"
)


def _스펙(**값):
    return QuerySpec.model_validate({"request_type": "REFINE", **값})


def _적용(키, category=None, 부모=None, 부모_결과=None, **값):
    스펙 = _스펙(category=category, **값)
    return 표.apply(스펙, [키], 부모 or 스펙, 부모_결과)


def test_BE_선택지와_키_문장이_같다():
    if not _BE_선택지.exists():
        pytest.skip("BE 소스가 없다")
    BE = dict(re.findall(r'^\s*([A-Z_]+)\("[^"]*",\s*"([^"]*)"\)', _BE_선택지.read_text(), re.M))
    assert BE == 표.PRESETS


def test_선택지_문장을_지우고_직접_쓴_문장만_남긴다():
    assert 표.strip_sentences("더 저렴한 제품으로, 무향 제품으로, 여름에 쓸 것") == "여름에 쓸 것"
    assert 표.strip_sentences("더 저렴한 제품으로") == ""
    assert 표.strip_sentences(" 여름용 ,  가벼운 ") == "여름용, 가벼운"
    assert 표.strip_sentences(None) == ""


# 더 저렴하게

def test_기준가는_이전_예산_상한이다():
    부모 = _스펙(budget={"max": 30000})
    결과 = 표.apply(부모, ["CHEAPER"], 부모, {"items": [{"price": 10000}]})
    assert 결과.budget.max == 24000


def test_예산이_없으면_이전_결과_상위_5개_가격의_중앙값이_기준가다():
    카드 = [{"price": p} for p in (20000, 31000, None, 25000, 40000, 99000)]
    결과 = _적용("CHEAPER", 부모_결과={"items": 카드})
    # 상위 5개 중 가격 있는 4개의 중앙값 28000 → 22400 → 천 원 단위 내림
    assert 결과.budget.max == 22000


def test_기준가가_없으면_문장_조건으로_둔다():
    결과 = _적용("CHEAPER", 부모_결과={"items": []})
    assert 결과.budget.max is None and 결과.conditions == ["저렴한"]


def test_세트_예산은_건드리지_않는다():
    결과 = _적용("CHEAPER", budget={"max": 30000, "total": 100000})
    assert 결과.budget.total == 100000 and 결과.budget.max == 24000


# 카테고리별 반영

@pytest.mark.parametrize("키, category, 특징, 조건", [
    ("UNSCENTED", "skincare", {"fragrance_free": True}, []),
    ("UNSCENTED", "base", {}, ["무향"]),
    ("HIGH_COVERAGE", "base", {"coverage": "높음"}, []),
    ("HIGH_COVERAGE", "lip", {}, ["커버력 높은"]),
    ("LONG_LASTING", "base", {"lasting_power": "높음"}, []),
    ("LONG_LASTING", "sun", {"lasting_power": "높음"}, []),
    ("LONG_LASTING", "lip", {"lasting_power": "높음"}, []),
    ("LONG_LASTING", "skincare", {}, ["지속력 좋은"]),
    ("UV_PROTECT", "sun", {}, ["자외선 차단"]),
    ("UV_PROTECT", "base", {}, ["자외선 차단"]),
    ("SENSITIVE_OK", "skincare", {"skin_type": "민감"}, []),
    ("SENSITIVE_OK", "base", {"skin_type": "민감"}, []),
    ("SENSITIVE_OK", "sun", {"skin_type": "민감"}, []),
    ("SENSITIVE_OK", "lip", {}, ["민감 피부"]),
    ("HIGH_COVERAGE", None, {}, ["커버력 높은"]),
])
def test_선택지를_카테고리에_맞춰_특징이나_문장_조건으로_둔다(키, category, 특징, 조건):
    결과 = _적용(키, category)
    assert 결과.features == 특징
    assert 결과.conditions == 조건


def test_있던_조건은_지키고_겹치지_않게_더한다():
    결과 = 표.apply(
        _스펙(category="base", features={"finish": "매트"}, conditions=["여름", "무향"]),
        ["UNSCENTED", "HIGH_COVERAGE", "UNSCENTED"], _스펙(), None,
    )
    assert 결과.features == {"finish": "매트", "coverage": "높음"}
    assert 결과.conditions == ["여름", "무향"]


def test_모르는_키는_건너뛴다():
    스펙 = _스펙(category="base")
    assert 표.apply(스펙, ["MYSTERY"], 스펙, None) == 스펙
