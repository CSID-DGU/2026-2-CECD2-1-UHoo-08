"""보유 제품의 아침 · 저녁 순서를 정한다. 입력이 같으면 결과가 같다.

시간대를 나눠야 하는 쌍(SEPARATE)은 한쪽을 아침, 한쪽을 저녁에 둔다. 어느 쪽을 저녁에
둘지는 성분으로 정한다. 충돌 규칙 문구(040_ingredient_seed.sql)와 같은 방향이다.

    레티노이드(레티놀, 레티닐팔미테이트)   빛에 약하다 → 저녁
    각질 제거 산(AHA · BHA · PHA)          레티노이드보다는 아침, 비타민C 보다는 저녁
    비타민C                                 낮의 산화 방지 → 아침

나누지 않아도 되는 스킨케어는 아침 · 저녁 모두에 둔다. 선케어는 아침에만 둔다.
메이크업(베이스 · 립 · 아이 · 치크)은 스킨케어 순서가 아니라 넣지 않는다.

순서는 바르는 단계 순이다. 묽은 것에서 진한 것으로, 선케어는 마지막.
"""
from __future__ import annotations

from typing import Any

# 클수록 저녁 쪽
_저녁_순위 = {
    "레티놀": 3, "레티닐팔미테이트": 3,
    "글라이콜릭애씨드": 2, "락틱애씨드": 2, "살리실릭애씨드": 2,
    "베타인살리실레이트": 2, "글루코노락톤": 2,
    "비타민C": 1, "비타민C유도체": 1,
}

_단계 = [
    ("토너", "패드", "미스트"),
    ("부스터", "에센스"),
    ("세럼", "앰플"),
    ("로션",),
    ("크림", "젤크림", "아이크림", "밤", "오일", "슬리핑팩"),
]
_선케어 = "sun"
_스킨케어 = "skincare"

TIP_AVOID = "같이 쓰지 않는 게 좋은 조합이 있어요. 하루씩 번갈아 쓰세요"
TIP_SEPARATE = "아침과 저녁으로 나눠 쓰면 함께 써도 괜찮아요"


def _순위(성분들: list[str]) -> int:
    return max((_저녁_순위.get(x, 0) for x in 성분들), default=0)


def _단계_순서(항목: dict) -> int:
    종류 = ((항목.get("feature_json") or {}).get("product_type") or "").replace(" ", "")
    for i, 묶음 in enumerate(_단계):
        if 종류 in 묶음:
            return i
    return len(_단계)


def build_schedule(items: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """items: inventory 항목. pairs: [{a_id, b_id, level, ingredient_a, ingredient_b}]

    a_id · b_id 는 user_product_id, ingredient_a 는 a 쪽 성분, ingredient_b 는 b 쪽 성분이다.
    """
    시간: dict[str, str] = {}
    for 쌍 in pairs:
        if 쌍["level"] != "SEPARATE":
            continue
        a, b = 쌍["a_id"], 쌍["b_id"]
        if a in 시간 or b in 시간:
            # 이미 정해진 제품이 있으면 남은 쪽을 반대 시간에 둔다
            정한, 남은 = (a, b) if a in 시간 else (b, a)
            시간.setdefault(남은, "morning" if 시간[정한] == "evening" else "evening")
            continue
        저녁_a = _순위([쌍["ingredient_a"]]) >= _순위([쌍["ingredient_b"]])
        시간[a], 시간[b] = ("evening", "morning") if 저녁_a else ("morning", "evening")

    아침, 저녁 = [], []
    for 항목 in sorted(items, key=lambda i: (_단계_순서(i), i.get("name") or "")):
        카테고리, upid, 이름 = 항목.get("category"), 항목.get("user_product_id"), 항목.get("name") or ""
        if 카테고리 == _스킨케어:
            정한 = 시간.get(upid)
            if 정한 != "evening":
                아침.append(이름)
            if 정한 != "morning":
                저녁.append(이름)
    아침 += [i.get("name") or "" for i in items if i.get("category") == _선케어]

    수준들 = {쌍["level"] for 쌍 in pairs}
    tip = TIP_AVOID if "AVOID" in 수준들 else TIP_SEPARATE if "SEPARATE" in 수준들 else None
    return {"morning": 아침, "evening": 저녁, "tip": tip}
