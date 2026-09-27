"""상품 마스터에 무엇이 채워져 있는지 센다.

v2 의 여러 기능이 상품 테이블의 특정 칸에 값이 있다는 것을 전제로 돈다.
그 칸이 비어 있으면 기능은 에러 없이 "결과 없음"으로 조용히 넘어간다.
착수 전에 무엇이 비었는지부터 눈으로 본다.

    성분(feature_json.key_ingredient)  없으면 PreFilter 의 충돌 제외가
                                       실데이터에서 한 번도 걸리지 않는다
    가격(original_price·lowest_price)  없으면 예산 적합도와 가성비가 계산되지 않는다
    임베딩(product_embeddings)          없으면 조건 탐색이 후보를 못 찾는다
    리뷰(review_count)                  없으면 후기 일치 점수가 빠진다

사용:
    cd AI
    python -m scripts.audit_product_master
    python -m scripts.audit_product_master --markdown --out eval/reports/product_master_20260927.md
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from datetime import date
from typing import Any

from db.supabase_client import get_supabase

PAGE = 1000


def _모두_읽기(table: str, columns: str) -> list[dict[str, Any]]:
    """테이블 전체를 페이지 단위로 읽는다. 기본 응답 한도가 1000행이라
    그냥 select 하면 조용히 잘린 수치를 보고 판단하게 된다."""
    sb = get_supabase()
    rows: list[dict[str, Any]] = []
    시작 = 0
    while True:
        묶음 = (
            sb.table(table).select(columns)
            .range(시작, 시작 + PAGE - 1)
            .execute()
        ).data or []
        rows.extend(묶음)
        if len(묶음) < PAGE:
            return rows
        시작 += PAGE


def _feature(row: dict) -> dict:
    """feature_json 은 행마다 dict 이거나 JSON 문자열이다."""
    값 = row.get("feature_json")
    if isinstance(값, str):
        try:
            값 = json.loads(값)
        except json.JSONDecodeError:
            return {}
    return 값 if isinstance(값, dict) else {}


def _표시폭(s: str) -> int:
    """한글은 터미널에서 두 칸을 차지한다. len() 으로 맞추면 표가 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _오른쪽(s: str, 폭: int) -> str:
    return " " * max(0, 폭 - _표시폭(s)) + s


def _왼쪽(s: str, 폭: int) -> str:
    return s + " " * max(0, 폭 - _표시폭(s))


def _비율(있음: int, 전체: int) -> str:
    if 전체 == 0:
        return "  -  "
    return f"{있음 / 전체 * 100:5.1f}%"


def 수집() -> dict[str, Any]:
    products = _모두_읽기(
        "products",
        "product_id, category, feature_json, original_price, lowest_price, review_count",
    )
    임베딩_id = {r["product_id"] for r in _모두_읽기("product_embeddings", "product_id")}

    카테고리별: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    성분_키: dict[str, int] = defaultdict(int)

    for r in products:
        cat = r.get("category") or "(없음)"
        칸 = 카테고리별[cat]
        칸["전체"] += 1

        feat = _feature(r)
        if feat:
            칸["feature_json"] += 1
        for k in feat:
            성분_키[k] += 1

        키성분 = feat.get("key_ingredient")
        if 키성분:
            칸["성분"] += 1
        if r.get("original_price") or r.get("lowest_price"):
            칸["가격"] += 1
        if r["product_id"] in 임베딩_id:
            칸["임베딩"] += 1
        if (r.get("review_count") or 0) > 0:
            칸["리뷰"] += 1

    return {
        "전체": len(products),
        "카테고리별": {k: dict(v) for k, v in 카테고리별.items()},
        "feature_키_빈도": dict(sorted(성분_키.items(), key=lambda kv: -kv[1])),
    }


항목 = ("feature_json", "성분", "가격", "임베딩", "리뷰")


def 텍스트로(결과: dict) -> str:
    줄 = [f"상품 마스터 현황  ({date.today()})", f"전체 상품 {결과['전체']}개", ""]
    머리 = _왼쪽("카테고리", 14) + _오른쪽("전체", 7) + "".join(_오른쪽(n, 14) for n in 항목)
    줄 += [머리, "-" * _표시폭(머리)]
    for cat, 칸 in sorted(결과["카테고리별"].items(), key=lambda kv: -kv[1]["전체"]):
        전체 = 칸["전체"]
        줄.append(
            _왼쪽(cat, 14) + _오른쪽(str(전체), 7)
            + "".join(_오른쪽(_비율(칸.get(n, 0), 전체).strip(), 14) for n in 항목)
        )
    줄 += ["", "feature_json 키 빈도"]
    for k, v in 결과["feature_키_빈도"].items():
        줄.append("  " + _왼쪽(k, 24) + _오른쪽(str(v), 7))
    return "\n".join(줄)


def 마크다운으로(결과: dict) -> str:
    줄 = [
        f"# 상품 마스터 현황 ({date.today()})",
        "",
        f"전체 상품 **{결과['전체']}개**",
        "",
        "| 카테고리 | 전체 | " + " | ".join(항목) + " |",
        "| --- | ---: | " + " | ".join("---:" for _ in 항목) + " |",
    ]
    for cat, 칸 in sorted(결과["카테고리별"].items(), key=lambda kv: -kv[1]["전체"]):
        전체 = 칸["전체"]
        줄.append(
            f"| {cat} | {전체} | "
            + " | ".join(_비율(칸.get(n, 0), 전체).strip() for n in 항목)
            + " |"
        )
    줄 += ["", "## feature_json 키 빈도", "", "| 키 | 상품 수 |", "| --- | ---: |"]
    for k, v in 결과["feature_키_빈도"].items():
        줄.append(f"| `{k}` | {v} |")
    줄 += [
        "",
        "## 읽는 법",
        "",
        "- **성분** 이 낮으면 PreFilter 의 충돌 제외가 실데이터에서 걸리지 않는다. "
        "규칙을 아무리 잘 만들어도 비교할 성분이 없다.",
        "- **가격** 이 낮으면 예산 적합도와 가성비 점수가 빠진다.",
        "- **임베딩** 이 낮으면 조건 탐색이 후보 자체를 못 찾는다.",
        "- **리뷰** 가 낮으면 후기 일치 점수가 빠진다.",
        "",
        "비율이 낮은 카테고리부터 마스터를 채운다.",
    ]
    return "\n".join(줄)


def main() -> None:
    ap = argparse.ArgumentParser(description="상품 마스터 채움 현황 점검")
    ap.add_argument("--markdown", action="store_true", help="리포트용 마크다운으로 출력")
    ap.add_argument("--out", help="결과를 파일로 저장")
    args = ap.parse_args()

    결과 = 수집()
    본문 = 마크다운으로(결과) if args.markdown else 텍스트로(결과)

    if args.out:
        from pathlib import Path
        Path(args.out).write_text(본문 + "\n", encoding="utf-8")
        print(f"저장: {args.out}")
    else:
        print(본문)


if __name__ == "__main__":
    main()
