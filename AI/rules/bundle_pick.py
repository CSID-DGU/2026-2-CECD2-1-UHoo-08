"""칸별 후보로 예산 안의 세트 조합을 고른다. 입력이 같으면 결과가 같다. DB 와 LLM 을 부르지 않는다.

칸마다 점수 상위 몇 개만 놓고 모든 조합을 센다. 칸이 다섯 개여도 6^5 = 7,776 개라
바로 끝난다. 조합 수가 상한을 넘으면 칸마다 놓는 후보 수를 줄인다.

── 조합의 성격 ───────────────────────────────────────────────────
예산 안의 조합 중에서 성격마다 하나씩 고른다. 같은 조합이 여러 성격에 뽑히면 한 번만 싣는다.

    균형형        평균 점수가 가장 높은 조합 (같으면 싼 쪽)
    알뜰형        균형형보다 평균 점수가 크게 떨어지지 않는(ALLOWED_DROP) 조합 중 가장 싼 것
    가성비형      만 원당 점수가 가장 높은 조합
    {핵심} 집중형  예산이 가장 큰 칸(세트의 핵심 단계)의 점수가 가장 높은 조합
    다른 조합     위에서 빠진 조합 중 평균 점수 순으로 채운다(최대 MAX_BUNDLES 개까지)

예산 안에 조합이 하나도 없으면 가장 싼 조합 하나를 싣고, 얼마나 넘는지 이유를 단다.
"""
from __future__ import annotations

from itertools import product
from math import prod
from typing import Any

MAX_BUNDLES = 5
PER_SLOT = 6
MAX_COMBOS = 50_000
ALLOWED_DROP = 10


def _평균(조합: tuple[dict, ...]) -> float:
    return sum(o["score"] for o in 조합) / len(조합)


def _합계(조합: tuple[dict, ...]) -> int:
    return sum(o["price"] for o in 조합)


def _놓을_수(칸들: list[dict]) -> int:
    n = PER_SLOT
    while n > 1 and prod(min(n, len(c["options"])) for c in 칸들) > MAX_COMBOS:
        n -= 1
    return n


def pick(slots: list[dict[str, Any]], budget: int | None) -> list[dict[str, Any]]:
    """slots: [{slot_key, label, amount, options: [{product_id, price, score}]}]

    options 는 가격을 아는 후보만, 점수 높은 순이다. 후보가 없는 칸은 빼고 조합한다.
    돌려주는 값: [{label, total_price, over_budget_reason, picks: [(slot, option), ...]}]
    """
    칸들 = [c for c in slots if c.get("options")]
    if not 칸들:
        return []
    n = _놓을_수(칸들)
    모든 = list(product(*[c["options"][:n] for c in 칸들]))

    def 담기(label: str, 조합: tuple[dict, ...], 이유: str | None = None) -> dict:
        return {"label": label, "total_price": _합계(조합), "over_budget_reason": 이유,
                "picks": list(zip(칸들, 조합))}

    안 = [c for c in 모든 if budget is None or _합계(c) <= budget]
    if not 안:
        싼 = min(모든, key=lambda c: (_합계(c), -_평균(c)))
        return [담기("최저가 조합", 싼,
                   f"예산 안에서 모든 칸을 채울 수 없어 가장 저렴한 조합을 골랐어요 "
                   f"({_합계(싼) - budget:,}원 초과)")]

    균형 = max(안, key=lambda c: (_평균(c), -_합계(c)))
    알뜰 = min((c for c in 안 if _평균(c) >= _평균(균형) - ALLOWED_DROP),
             key=lambda c: (_합계(c), -_평균(c)))
    가성비 = max(안, key=lambda c: (_평균(c) / max(_합계(c), 1), _평균(c)))
    핵심 = max(range(len(칸들)), key=lambda i: (칸들[i].get("amount") or 0, -i))
    집중 = max(안, key=lambda c: (c[핵심]["score"], _평균(c), -_합계(c)))

    고른: list[tuple[str, tuple]] = [
        ("균형형", 균형), ("알뜰형", 알뜰), ("가성비형", 가성비),
        (f"{칸들[핵심]['label']} 집중형", 집중),
    ]
    for c in sorted(안, key=lambda c: (-_평균(c), _합계(c))):
        고른.append(("다른 조합", c))

    결과, 본 = [], set()
    for label, 조합 in 고른:
        키 = tuple(o["product_id"] for o in 조합)
        if 키 in 본:
            continue
        본.add(키)
        결과.append(담기(label, 조합))
        if len(결과) == MAX_BUNDLES:
            break
    return 결과
