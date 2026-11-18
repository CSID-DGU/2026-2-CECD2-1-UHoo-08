"""
products 가격·리뷰 데이터 백필.

lowest_price·stores·review_summary 등이 비어 있는 상품을 찾아 Gemini 보강을
돌리고 저장한다. 상품 상세 화면에서 최저가·할인·리뷰 요약이 통째로 비어 보이는
것은 시딩 당시 이 값들이 채워지지 않았기 때문이다.

    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --dry-run
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --limit 10 --workers 2

--types 는 제품 종류를 다시 채운다. 종류가 비었거나 카테고리의 종류 목록에 없는 상품,
카테고리가 목록에 없는 상품(blush, 빈 값)만 골라 다시 추출한다. 가격, 리뷰는 그대로 둔다.
보강 결과를 통째로 저장하면 가격, 리뷰가 새 값으로 바뀌고 리뷰 임베딩도 다시 만들어지기
때문이다. 카테고리는 그대로이면 종류만 바꾸고, 카테고리가 바뀌면 특징 스키마가 달라
특징을 통째로 바꾼다. 끝나면 상품 임베딩을 다시 만든다(scripts/reembed_products.py).

    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --types --dry-run
    PYTHONPATH=. ./venv/bin/python scripts/backfill_product_data.py --types
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from agents.product_agent.gemini_enricher import enrich_product
from agents.product_agent.product_repository import save_enriched
from db.supabase_client import get_supabase
from models.extracted_product import ExtractedProduct
from rules.product_types import CATEGORY_TYPES, product_types

# 이 중 하나라도 비어 있으면 상세 화면에 빈칸이 생긴다.
_REQUIRED = ("lowest_price", "stores", "review_summary", "average_score")

# 예전에 쓰던 카테고리 값과 지금 카테고리
_LEGACY_CATEGORY = {"blush": "cheek"}


def _is_blank(value) -> bool:
    return value in (None, "", [], {})


def _needs_data(row: dict) -> bool:
    return any(_is_blank(row.get(f)) for f in _REQUIRED)


def _feature(row: dict) -> dict:
    feat = row.get("feature_json")
    if isinstance(feat, str):
        try:
            feat = json.loads(feat)
        except (ValueError, TypeError):
            return {}
    return feat if isinstance(feat, dict) else {}


def _product_type(row: dict) -> Optional[str]:
    """추출에 힌트로 넘길 종류. 종류가 여럿이면 첫 번째를 쓴다."""
    value = _feature(row).get("product_type")
    if isinstance(value, list):
        value = next(iter(value), None)
    return value if isinstance(value, str) else None


def _needs_types(row: dict) -> bool:
    """카테고리가 목록에 없거나, 그 카테고리의 종류를 하나도 모르면 다시 채운다."""
    category = row.get("category")
    if category not in CATEGORY_TYPES:
        return True
    return not product_types(_feature(row), category)


def _known_category(row: dict) -> Optional[str]:
    """이름을 보지 않고 정할 수 있는 카테고리. 정할 수 없으면 None."""
    category = row.get("category") or ""
    return category if category in CATEGORY_TYPES else _LEGACY_CATEGORY.get(category)


def _classify_category(row: dict) -> Optional[str]:
    """제품 등록과 같은 파서로 상품 이름을 보고 카테고리를 정한다."""
    from agents.input_agent.text_parser import parse_text

    parsed = parse_text(f"{row.get('brand') or ''} {row.get('name') or ''}".strip())
    main = (parsed.category or {}).get("main")
    return main if main in CATEGORY_TYPES else None


def _stored_types(value, category: str):
    """저장할 종류. 표준 이름 하나는 문자열로, 둘이면 목록으로, 모르면 None."""
    types = product_types({"product_type": value}, category)
    if not types:
        return None
    return types[0] if len(types) == 1 else types


def _targets(include_all: bool, types_only: bool = False) -> List[dict]:
    res = (
        get_supabase()
        .table("products")
        .select(
            "product_id, name, brand, category, feature_json, "
            "lowest_price, stores, review_summary, average_score"
        )
        .order("name")
        .execute()
    )
    rows = res.data or []
    if types_only:
        return [r for r in rows if _needs_types(r)]
    return rows if include_all else [r for r in rows if _needs_data(r)]


def _enrich_one(row: dict) -> None:
    extracted = ExtractedProduct(
        product_name=row.get("name"),
        brand=row.get("brand"),
        category={
            "main": row.get("category") or "skincare",
            "sub": _product_type(row) or "",
        },
    )
    save_enriched(row["product_id"], enrich_product(extracted))


def _refill_types(row: dict) -> str:
    """종류를 다시 추출해 특징과 카테고리만 저장한다. 저장한 카테고리와 종류를 돌려준다."""
    category = _known_category(row) or _classify_category(row)
    if category is None:
        raise ValueError("카테고리를 정하지 못했다")

    extracted = ExtractedProduct(
        product_name=row.get("name"),
        brand=row.get("brand"),
        category={"main": category, "sub": _product_type(row) or ""},
    )
    features = enrich_product(extracted).get("product_features") or {}
    if not features:
        raise ValueError("특징을 받지 못했다")
    new_type = _stored_types(features.get("product_type"), category)

    if category != row.get("category"):
        payload = {
            "category": category,
            "feature_json": json.dumps({**features, "product_type": new_type}, ensure_ascii=False),
        }
    elif new_type is None:
        raise ValueError(f"목록에 있는 종류를 찾지 못했다({features.get('product_type')!r})")
    else:
        # 다른 특징은 그대로 둔다. 평가와 점수가 지금 값을 보고 있다
        payload = {
            "feature_json": json.dumps({**_feature(row), "product_type": new_type}, ensure_ascii=False),
        }
    get_supabase().table("products").update(payload).eq("product_id", row["product_id"]).execute()
    return f"{category} {new_type}"


def _describe_types(row: dict) -> str:
    category = row.get("category") or "(없음)"
    known = _known_category(row)
    to = known if known else "이름으로 판단"
    move = f"{category} → {to}" if to != category else category
    return f"{move}, 종류: {_feature(row).get('product_type')!r}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="대상만 출력하고 끝낸다")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 상품 수 (0=전체)")
    parser.add_argument("--workers", type=int, default=3, help="동시 처리 수")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="이미 채워진 상품까지 다시 수집")
    mode.add_argument(
        "--types", action="store_true",
        help="종류가 비었거나 목록 밖인 상품, 카테고리가 목록 밖인 상품만 종류를 다시 추출한다",
    )
    args = parser.parse_args()

    targets = _targets(include_all=args.all, types_only=args.types)
    if args.limit:
        targets = targets[: args.limit]

    print(f"대상 {len(targets)}건")
    if args.dry_run:
        for row in targets:
            if args.types:
                print(f"  {row['brand']} {row['name']} — {_describe_types(row)}")
                continue
            missing = [f for f in _REQUIRED if _is_blank(row.get(f))]
            print(f"  {row['brand']} {row['name']} — 없음: {', '.join(missing) or '없음'}")
        return
    if not targets:
        return
    if args.types:
        _run(targets, _refill_types, args.workers)
        print("상품 임베딩을 다시 만든다: PYTHONPATH=. ./venv/bin/python scripts/reembed_products.py")
        return

    # 리뷰 임베딩 모델을 미리 한 번 올린다. 워커들이 동시에 처음 로드하면
    # 경쟁 상태로 세그폴트가 난다(실제로 워커 4개에서 exit 139로 죽었다).
    try:
        from services.embedding_service import EmbeddingService
        EmbeddingService.get()
    except Exception as e:
        print(f"임베딩 모델 준비 실패(계속 진행): {type(e).__name__} {e}")

    _run(targets, _enrich_one, args.workers)


def _run(targets: List[dict], work, workers: int) -> None:
    succeeded = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, row): row for row in targets}
        for done in as_completed(futures):
            row = futures[done]
            try:
                result = done.result()
            except Exception as e:
                print(f"  ✗ {row['brand']} {row['name']}: {type(e).__name__} {e}")
                continue
            succeeded += 1
            print(f"  ✓ {row['brand']} {row['name']}" + (f" — {result}" if result else ""))

    print(f"\n완료: {succeeded}/{len(targets)}")


if __name__ == "__main__":
    main()
