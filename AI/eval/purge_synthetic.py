"""합성 사용자를 전부 지운다.

users.is_synthetic 이 켜진 사람만 본다. 실제 사용자는 건드리지 않는다.

    python -m eval.purge_synthetic          지울 대상을 보여주고 묻는다
    python -m eval.purge_synthetic --yes    묻지 않고 지운다

지우는 일이라 기본값을 "묻는다"로 둔다. 실제 사용자 테이블을 건드리는
스크립트가 아무 확인 없이 도는 것은 위험하다.
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(description="합성 사용자 일괄 삭제")
    ap.add_argument("--yes", action="store_true", help="확인 없이 지운다")
    args = ap.parse_args()

    from db.supabase_client import get_supabase

    sb = get_supabase()
    사용자 = (sb.table("users").select("id, name")
              .eq("is_synthetic", True).execute()).data or []

    if not 사용자:
        print("합성 사용자가 없다.")
        return

    print(f"합성 사용자 {len(사용자)}명:")
    for u in 사용자[:10]:
        print(f"  {u['id']}  {u.get('name')}")
    if len(사용자) > 10:
        print(f"  … 외 {len(사용자) - 10}명")

    if not args.yes:
        if input("지울까요? [y/N] ").strip().lower() not in ("y", "yes"):
            print("그만둔다.")
            return

    ids = [u["id"] for u in 사용자]
    # 보유 제품을 먼저 지운다. 사용자를 먼저 지우면 주인 없는 행이 남는다.
    sb.table("user_products").delete().in_("user_id", ids).execute()
    sb.table("users").delete().in_("id", ids).execute()
    print(f"{len(ids)}명을 지웠다.")


if __name__ == "__main__":
    main()
