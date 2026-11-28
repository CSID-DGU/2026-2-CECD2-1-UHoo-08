"""총예산을 세트의 칸마다 나눈다. 입력이 같으면 결과가 같다.

칸 금액은 검색의 상한이 아니다(Retrieve 는 칸 가격 상한을 걸지 않는다). Bundle 이 조합을
고를 때 "이 칸이 세트에서 얼마쯤을 차지하는 게 보통인지" 보는 기준이고, 가장 큰 칸이
세트의 핵심 단계가 된다(집중형 조합).

비중은 제품 종류의 보통 가격대를 따른다. 세럼 · 앰플 · 크림은 토너보다 비싸다.
모르는 종류는 1 이다.
"""
from __future__ import annotations

from typing import Any

from rules.product_types import canonical

# 제품 종류 → 칸 키. 화면 주소(/bundles/{i}/slots/{slotKey})에 들어가므로 영문으로 둔다.
SLOT_KEYS: dict[str, str] = {
    "토너": "toner", "패드": "pad", "미스트": "mist", "부스터": "booster",
    "에센스": "essence", "세럼": "serum", "앰플": "ampoule", "로션": "lotion",
    "크림": "cream", "젤크림": "gel_cream", "아이크림": "eye_cream", "밤": "balm", "오일": "oil",
    "시트마스크": "mask", "슬리핑팩": "sleeping_pack",
    "선크림": "sunscreen", "선스틱": "sun_stick", "선쿠션": "sun_cushion",
    "쿠션": "cushion", "파운데이션": "foundation", "컨실러": "concealer", "프라이머": "primer",
    "립스틱": "lipstick", "립틴트": "lip_tint", "립밤": "lip_balm", "립글로스": "lip_gloss",
}

WEIGHTS: dict[str, float] = {
    "미스트": 0.8, "토너": 1.0, "패드": 1.0, "부스터": 1.1, "에센스": 1.2, "로션": 1.0,
    "세럼": 1.5, "앰플": 1.5, "크림": 1.4, "젤크림": 1.3, "아이크림": 1.4, "오일": 1.2,
    "선크림": 1.0, "선스틱": 1.0, "쿠션": 1.4, "파운데이션": 1.5, "컨실러": 0.9,
    "립밤": 0.6, "립틴트": 0.8, "립스틱": 0.9, "립글로스": 0.8,
}

_반올림 = 100


def _종류(step: dict) -> str | None:
    종류 = step.get("product_type")
    if not 종류:
        return None
    return canonical(종류, step.get("category")) or 종류


def split(total: int, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{slot_key, label, category, product_type, amount}]. 금액 합은 total 과 같다.

    steps 는 QuerySpec.bundle_steps(model_dump) 다. 같은 종류가 두 번 나오면 칸 키에 번호를 붙인다.
    """
    if not steps or not total:
        return []
    종류들 = [_종류(s) for s in steps]
    무게 = [WEIGHTS.get(t or "", 1.0) for t in 종류들]
    합 = sum(무게)

    칸들, 쓴_키 = [], set()
    for i, (step, 종류, w) in enumerate(zip(steps, 종류들, 무게)):
        키 = SLOT_KEYS.get(종류 or "", f"slot{i + 1}")
        기본 = 키
        n = 2
        while 키 in 쓴_키:
            키, n = f"{기본}_{n}", n + 1
        쓴_키.add(키)
        칸들.append({
            "slot_key": 키,
            "label": step.get("label") or 종류 or f"{i + 1}단계",
            "category": step.get("category"),
            "product_type": 종류,
            "amount": round(total * w / 합 / _반올림) * _반올림,
        })
    # 반올림으로 생긴 차이는 가장 큰 칸이 맡는다. 합이 예산과 정확히 같아야 화면 숫자가 맞는다
    칸들[max(range(len(칸들)), key=lambda i: 칸들[i]["amount"])]["amount"] += total - sum(c["amount"] for c in 칸들)
    return 칸들
