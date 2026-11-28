"""칸별 후보로 예산 안의 세트 조합을 고른다. 고르는 규칙은 rules/bundle_pick.py.

READS:  budget_plan, candidates, scored, product_meta, query_spec
WRITES: bundles, bundle_slots

    bundles       contracts.result.BundleOption 모양의 dict. Compose 가 그대로 싣는다
    bundle_slots  칸마다 바꿀 수 있는 후보 (BundleSlot, by_alias). 스냅샷에 남아
                  BE 가 칸 교체 후보 · 교체 합계를 이것으로 계산한다

칸은 Retrieve 칸별 검색이 후보에 붙인 slot_key 로 안다. 가격을 모르는 후보는 쓰지 않는다.
합계를 낼 수 없고, 교체 후보로도 보여 줄 수 없다(BundleSlotCandidate 계약).
"""
from __future__ import annotations

import logging

from contracts.result import BundleSlot, BundleSlotCandidate
from graph.state import GraphState
from rules.bundle_pick import pick

logger = logging.getLogger(__name__)

# 칸 교체 화면에 보여 줄 후보 수
교체_후보_수 = 10


def slot_options(state: GraphState) -> list[dict]:
    """budget_plan 순서대로 칸마다 [{product_id, price, score, name}] (점수 높은 순)."""
    점수 = {s["product_id"]: s for s in state.get("scored") or []}
    메타 = state.get("product_meta") or {}
    칸_of: dict[str, str] = {}
    for 후보 in state.get("candidates") or []:
        if 후보.get("slot_key"):
            칸_of.setdefault(후보["product_id"], 후보["slot_key"])

    칸들 = []
    for 칸 in state.get("budget_plan") or []:
        옵션 = []
        for pid, s in 점수.items():
            가격 = (메타.get(pid) or {}).get("price")
            if 칸_of.get(pid) != 칸["slot_key"] or 가격 is None:
                continue
            옵션.append({"product_id": pid, "price": int(가격), "score": int(s["total"]),
                       "name": (메타.get(pid) or {}).get("name") or ""})
        옵션.sort(key=lambda o: (-o["score"], o["price"], o["product_id"]))
        칸들.append({**칸, "options": 옵션})
    return 칸들


def _카드(칸: dict, 옵션: dict, 점수: dict, 메타: dict) -> dict:
    m = 메타.get(옵션["product_id"]) or {}
    return {
        "product_id": 옵션["product_id"],
        "name": m.get("name") or "",
        "brand": m.get("brand") or "",
        "image_url": m.get("image_url"),
        "price": 옵션["price"],
        "total_score": 옵션["score"],
        "breakdown": (점수.get(옵션["product_id"]) or {}).get("breakdown") or [],
        "slot_key": 칸["slot_key"],
        "slot_label": 칸["label"],
    }


async def bundle(state: GraphState) -> dict:
    칸들 = slot_options(state)
    총액 = ((state.get("query_spec") or {}).get("budget") or {}).get("total")
    고른 = pick(칸들, 총액)

    빈_칸 = [c["label"] for c in 칸들 if not c["options"]]
    if 빈_칸:
        logger.warning("bundle: 후보가 없는 칸 %s 는 빼고 조합했다.", 빈_칸)

    점수 = {s["product_id"]: s for s in state.get("scored") or []}
    메타 = state.get("product_meta") or {}
    세트들 = [
        {
            "label": b["label"],
            "total_price": b["total_price"],
            "over_budget_reason": b["over_budget_reason"],
            "items": [_카드(칸, 옵션, 점수, 메타) for 칸, 옵션 in b["picks"]],
        }
        for b in 고른
    ]
    교체_후보 = [
        BundleSlot(
            slot_key=c["slot_key"], label=c["label"],
            candidates=[BundleSlotCandidate(product_id=o["product_id"], name=o["name"],
                                            price=o["price"], score=o["score"])
                        for o in c["options"][:교체_후보_수]],
        ).model_dump(by_alias=True)
        for c in 칸들 if c["options"]
    ]
    logger.info("bundle: 칸 %d개, 조합 %d개 %s", len(칸들), len(세트들), [b["label"] for b in 세트들])
    return {"bundles": 세트들, "bundle_slots": 교체_후보}
