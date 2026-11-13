"""추천 후보를 보유 제품과 견줘 거른다.

    이미 쓰고 있는 제품          빼고 OWNED 로 남긴다
    함께 쓰면 안 되는 성분 조합   빼고 CONFLICT 로 남긴다 (AVOID 가 하나라도 있으면)
    시간대를 나누면 되는 조합     남기고 배지를 단다 (SEPARATE 만 있으면)
    성분을 모르는 상품           남긴다. 모른다고 빼면 성분 정보가 없는 상품은 영영 추천되지 않는다

뺀 후보는 버리지 않는다. 화면에 "보유 제품과 충돌해 N개 제외"로 보여 줘야 사용자가
결과를 납득한다.

사용자가 직접 물은 상품(상품 평가의 기준 상품)은 빼지 않는다. 같은 판정을
base_conflicts 로 따로 돌려주고, 추천 이유 문장에서 알린다.

DB, LLM 없이 받은 값만으로 판정한다. 충돌 쌍은 부른 쪽이 성분 규칙으로 미리 구해 넘긴다.
"""
from __future__ import annotations

from typing import Any, NamedTuple

함께_쓰지_않음 = "AVOID"
시간대_나눔 = "SEPARATE"

보유_문구 = "이미 쓰고 계신 제품이에요"


class 거른_결과(NamedTuple):
    candidates: list[dict]                  # 남은 후보. 받은 순서를 지킨다
    excluded: list[dict]                    # {product_id, name, reason, detail}
    conflict_marks: dict[str, list[dict]]   # 남긴 후보의 배지용 충돌
    base_conflicts: dict[str, dict]         # 빼지 않은 상품의 판정. {owned, conflicts}


def _과와(이름: str) -> str:
    """이름 뒤에 붙일 조사. 받침이 있으면 '과', 없으면 '와'."""
    끝 = 이름.strip()[-1:] if 이름 else ""
    if "가" <= 끝 <= "힣":
        return "과" if (ord(끝) - ord("가")) % 28 else "와"
    return "와"


def _붙여(이름: str) -> str:
    return f"{이름}{_과와(이름)}"


def _표시(쌍: dict, 이름들: dict[str, str]) -> dict:
    """충돌 쌍 하나를 화면에 쓸 모양으로 바꾼다."""
    보유_id = 쌍.get("user_product_id")
    이름 = 이름들.get(보유_id) or "쓰고 계신 제품"
    수준 = 쌍.get("level")
    조언 = 쌍.get("advice")
    if not 조언:
        조언 = (
            f"{_붙여(이름)} 시간대를 나눠 쓰세요" if 수준 == 시간대_나눔
            else f"{_붙여(이름)} 함께 쓰지 않는 게 좋아요"
        )
    return {"user_product_id": 보유_id, "name": 이름, "level": 수준, "advice": 조언}


def _보유_제품별로(표시들: list[dict]) -> list[dict]:
    """같은 보유 제품과 걸린 쌍이 여럿이면 처음 것 하나만 남긴다. 배지가 겹쳐 보이지 않게 한다."""
    본: set = set()
    결과 = []
    for 표시 in 표시들:
        if 표시["user_product_id"] in 본:
            continue
        본.add(표시["user_product_id"])
        결과.append(표시)
    return 결과


def apply(
    candidates: list[dict],
    inventory: list[dict],
    conflicts: dict[str, list[dict]],
    names: dict[str, str],
    *,
    keep_ids: set[str] | frozenset[str] = frozenset(),
) -> 거른_결과:
    """후보를 거른다.

    conflicts   상품 id → 보유 제품과 걸린 성분 쌍 (check_compatibility 결과)
    names       상품 id → 상품 이름. 뺀 후보에 이름을 붙이는 데 쓴다
    keep_ids    빼지 않을 상품 id

    같은 상품이 여러 번 있으면(세트의 칸마다 찾은 후보) 모두 같은 판정을 받는다.
    뺀 기록은 상품마다 한 번만 남긴다.
    """
    보유_상품 = {항목.get("product_id") for 항목 in inventory if 항목.get("product_id")}
    보유_이름 = {
        항목.get("user_product_id"): 항목.get("name")
        for 항목 in inventory if 항목.get("user_product_id")
    }

    남은: list[dict] = []
    뺀: list[dict] = []
    뺀_id: set[str] = set()
    배지: dict[str, list[dict]] = {}
    기준: dict[str, dict] = {}

    for 후보 in candidates:
        pid = 후보["product_id"]
        표시들 = _보유_제품별로([_표시(쌍, 보유_이름) for 쌍 in conflicts.get(pid) or []])
        피할 = [표시 for 표시 in 표시들 if 표시["level"] == 함께_쓰지_않음]
        나눌 = [표시 for 표시 in 표시들 if 표시["level"] == 시간대_나눔]
        보유 = pid in 보유_상품

        if pid in keep_ids:
            if 보유 or 표시들:
                기준[pid] = {"owned": 보유, "conflicts": 표시들}
            남은.append(후보)
            continue

        if 보유 or 피할:
            if pid not in 뺀_id:
                뺀_id.add(pid)
                뺀.append({
                    "product_id": pid,
                    "name": names.get(pid),
                    "reason": "OWNED" if 보유 else "CONFLICT",
                    "detail": 보유_문구 if 보유 else f"{_붙여(피할[0]['name'])} 함께 쓰지 않는 게 좋아요",
                })
            continue

        if 나눌:
            배지[pid] = 나눌
        남은.append(후보)

    return 거른_결과(남은, 뺀, 배지, 기준)
