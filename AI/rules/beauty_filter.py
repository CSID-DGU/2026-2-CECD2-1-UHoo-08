"""뷰티와 무관한 게시물 거르기 (규칙, LLM 없음, 같은 입력이면 같은 결과).

ProductMatcher v2 에서 LLM 추출을 부르기 전에 돈다. 화장품 브랜드도, 화장품 종류 말도 없는 글은 LLM 에 보내지 않는다.
판정은 보수적으로 한다. 신호가 하나라도 있으면 LLM 에 보낸다(놓치는 쪽보다 한 번 더 부르는 쪽이 싸다).

신호
  brand      브랜드 사전(data/brand_dictionary.json)의 브랜드가 캡션에 있음 (공식 계정명 포함)
  type_word  화장품 종류 말(틴트 · 세럼 · 쿠션 · 샴푸 …)로 끝나는 단어 · 해시태그가 있음
  beauty_tag 뷰티 해시태그 (#메이크업 #올리브영 #grwm …)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rules.brand_resolve import BrandDictionary
from rules.mention_extract import type_of

FILTER_VERSION = "beauty-filter-v1"

_BEAUTY_TAGS = ("메이크업", "makeup", "올리브영", "올영", "grwm", "뷰티", "beauty", "화장품", "코덕", "스킨케어", "skincare",
                "데일리메이크업", "겟레디", "기초", "피부관리", "퍼스널컬러", "웜톤", "쿨톤", "립추천", "쿠션추천")


@dataclass
class BeautySignal:
    brands: list[str] = field(default_factory=list)
    type_words: list[str] = field(default_factory=list)
    beauty_tags: list[str] = field(default_factory=list)
    version: str = FILTER_VERSION

    @property
    def is_beauty(self) -> bool:
        return bool(self.brands or self.type_words or self.beauty_tags)


def beauty_signal(caption: str, d: BrandDictionary) -> BeautySignal:
    cap = caption or ""
    brands = [b.ko or b.en for _, b in d.find(cap)]
    words = re.split(r"[\s#,.!?~()\[\]·/]+", cap)
    types = sorted({tw for w in words if w and (tw := type_of(w)[0])})
    tags = [t for t in re.findall(r"#([0-9A-Za-z가-힣_]+)", cap) if any(k in t.lower() for k in _BEAUTY_TAGS)]
    return BeautySignal(brands, types, tags)
