"""성분 표기를 알아보는 키로 정규화한다.

성분 이름은 표기가 제각각이다. 나이아신아마이드·니아신아마이드·Niacinamide·
비타민B3 가 모두 같은 것을 가리킨다. `ingredient_alias` 테이블의 alias 컬럼은
소문자로 바꾸고 공백·하이픈·가운뎃점을 뺀 키로 저장돼 있다
(db/migrations/026_ingredient_rules.sql). 여기서 같은 규칙으로 원문을 키로
바꾼다. 조회하는 쪽도 이 함수를 거쳐야 같은 성분을 찾는다.

입력이 같으면 출력이 같아야 한다. LLM을 부르지 않는다.
"""
from __future__ import annotations

_STRIP_CHARS = (" ", "-", "·")  # 공백, 하이픈, 가운뎃점(·)


def normalize_key(raw: str) -> str:
    """조회 키로 바꾼다. 소문자, 공백·하이픈·가운뎃점 제거."""
    key = (raw or "").strip().lower()
    for ch in _STRIP_CHARS:
        key = key.replace(ch, "")
    return key


def resolve_canonical(raw_names: list[str], alias_map: dict[str, str]) -> list[str]:
    """원문 성분명 목록을 표준명으로 바꾼다.

    alias_map 은 normalize_key 로 만든 키 → 표준명이다(DB 조회 결과를 그대로 받는다).
    사전에 없는 성분은 원문을 그대로 쓴다. 조용히 빼면 PreFilter·Compatibility가
    "이 사람은 이 성분이 없다"고 오판한다 — 모르는 것과 없는 것은 다르다.

    순서를 유지하고 중복을 없앤다.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_names:
        name = (raw or "").strip()
        if not name:
            continue
        canonical = alias_map.get(normalize_key(name), name)
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out
