"""합성 페르소나를 DB 에 넣는다.

시나리오를 실제로 태워 보려면 사용자와 보유 제품이 DB 에 있어야 한다.
PreFilter 도 홈 카드도 테이블을 읽지, JSONL 을 읽지 않는다.

    python -m eval.load_synthetic
    python -m eval.load_synthetic --only persona-0003

넣은 사용자는 users.is_synthetic 으로 표시된다. purge_synthetic 이 이 표시만
보고 지우므로 실제 사용자는 건드리지 않는다.

같은 페르소나를 다시 넣으면 덮어쓴다. 사용자 id 를 페르소나 id 에서 항상
같은 값으로 만들기 때문이다. 그래야 데이터를 고치고 다시 넣어도 같은 사람이
여럿 생기지 않는다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 파일을
열어 보지도 못한다.
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERSONA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "personas"

# 페르소나 id → 사용자 id 를 만들 때 쓰는 고정 이름공간.
# 값 자체에 의미는 없고, 바꾸면 이전에 넣은 사용자와 이어지지 않는다.
_NAMESPACE = uuid.UUID("6f1b2f7c-2c5a-4f0e-9a3e-0d4c8b9a1e77")


def synthetic_user_id(persona_id: str) -> str:
    """페르소나 id 하나에 항상 같은 사용자 id 를 준다."""
    return str(uuid.uuid5(_NAMESPACE, persona_id))


def read_personas(only: str | None = None) -> list[dict[str, Any]]:
    페르소나: list[dict[str, Any]] = []
    for path in sorted(PERSONA_DIR.glob("*.jsonl")):
        for 줄 in path.read_text(encoding="utf-8").splitlines():
            if not 줄.strip():
                continue
            rec = json.loads(줄)
            if only is None or rec.get("id") == only:
                페르소나.append(rec)
    return 페르소나


def _사용자_행(rec: dict) -> dict:
    지금 = datetime.now(timezone.utc).isoformat()
    return {
        "id": synthetic_user_id(rec["id"]),
        # 화면과 로그에서 합성 사용자임이 바로 보이게 한다.
        "name": f"합성 {rec['id']}",
        "provider": "synthetic",
        "onboarding_completed": True,
        "personal_color": rec.get("personal_color"),
        "skin_type": rec.get("skin_type"),
        "skin_concerns": rec.get("skin_concerns") or [],
        "region": rec.get("region"),
        "is_synthetic": True,
        "created_at": 지금,
        "updated_at": 지금,
    }


def _보유_행(user_id: str, 보유: dict) -> dict:
    지금 = datetime.now(timezone.utc).isoformat()
    행 = {
        "user_id": user_id,
        "product_id": 보유["product_id"],
        "usage_type": 보유.get("usage_type", "USING"),
        "source": "MANUAL",
        "created_at": 지금,
        "updated_at": 지금,
    }
    for 키 in ("opened_at", "purchased_at", "expiry_date", "pao_months",
               "remaining_pct", "rating"):
        if 보유.get(키) is not None:
            행[키] = 보유[키]
    return 행


def main() -> None:
    ap = argparse.ArgumentParser(description="합성 페르소나를 DB 에 적재")
    ap.add_argument("--only", help="페르소나 id 하나만 넣는다")
    args = ap.parse_args()

    from db.supabase_client import get_supabase

    페르소나 = read_personas(args.only)
    if not 페르소나:
        print(f"넣을 페르소나가 없다: {PERSONA_DIR}")
        return

    sb = get_supabase()
    보유_수 = 0

    for rec in 페르소나:
        user_id = synthetic_user_id(rec["id"])
        sb.table("users").upsert(_사용자_행(rec)).execute()

        # 다시 넣기 전에 이 사용자의 보유 제품을 비운다. 그러지 않으면
        # 데이터를 고쳐 다시 넣을 때 옛 행이 남아 둘이 섞인다.
        sb.table("user_products").delete().eq("user_id", user_id).execute()

        보유 = [_보유_행(user_id, b) for b in rec.get("inventory") or []]
        if 보유:
            sb.table("user_products").insert(보유).execute()
            보유_수 += len(보유)

    print(f"사용자 {len(페르소나)}명, 보유 제품 {보유_수}개를 넣었다.")


if __name__ == "__main__":
    main()
