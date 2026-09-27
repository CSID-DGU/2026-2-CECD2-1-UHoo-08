"""합성 데이터와 골든셋의 형식을 검사한다.

형식이 어긋나도 파일은 그냥 읽힌다. 그래서 어긋남은 데이터를 쓰는 쪽에서
"결과가 이상한데 왜인지 모르겠다"로 나타난다. 가장 자주 겪게 될 것은
상품 마스터에 없는 product_id 다. 적재까지는 되지만 PreFilter 가 그 제품을
찾지 못해, 보유 제품이 하나도 없는 사람처럼 동작한다.

    python -m eval.validate         형식만 본다. DB 없이 돈다
    python -m eval.validate --db    product_id 가 실제로 있는지까지 본다

규칙은 eval/README.md 에 적혀 있다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent

SYNTHETIC = AI_ROOT / "data" / "synthetic"
GOLDEN = AI_ROOT / "eval" / "golden"

# 폴더 이름 → id 접두어. 폴더 이름을 그대로 쓰면 personas-0001 처럼 읽히므로
# 네 곳만 따로 적는다. 골든셋은 폴더 이름 뒤에 -g 를 붙인다.
SYNTHETIC_PREFIX = {
    "personas": "persona",
    "queries": "query",
    "feedback": "feedback",
    "env": "env",
}

SPLITS = {"dev", "test"}
SOURCES = {"claude", "manual", "real"}
CHECKS = {"exact", "contains", "property"}
USAGE_TYPES = {"USING", "ONBOARDING", "USED", "DISCARDED", "INTERESTED", "VIEWED"}


def _접두어(path: Path) -> str | None:
    """이 파일의 레코드가 가져야 할 id 접두어."""
    try:
        상대 = path.relative_to(AI_ROOT)
    except ValueError:
        return None
    부분 = 상대.parts
    if 부분[:2] == ("data", "synthetic") and len(부분) > 3:
        return SYNTHETIC_PREFIX.get(부분[2])
    if 부분[:2] == ("eval", "golden") and len(부분) > 3:
        return f"{부분[2]}-g"
    return None


def _레코드_검사(rec: dict, 접두어: str, 골든: bool) -> list[str]:
    문제: list[str] = []

    아이디 = rec.get("id")
    if not isinstance(아이디, str):
        문제.append("id 가 없다")
    elif not re.fullmatch(rf"{re.escape(접두어)}-\d{{4,}}", 아이디):
        문제.append(f"id 가 {접두어}-0001 모양이 아니다: {아이디!r}")

    if rec.get("split") not in SPLITS:
        문제.append(f"split 은 dev 또는 test 다: {rec.get('split')!r}")
    if rec.get("source") not in SOURCES:
        문제.append(f"source 는 claude·manual·real 중 하나다: {rec.get('source')!r}")

    if 골든:
        for 키 in ("input", "expected", "check"):
            if 키 not in rec:
                문제.append(f"골든셋인데 {키} 가 없다")
        if "check" in rec and rec["check"] not in CHECKS:
            문제.append(f"check 는 exact·contains·property 중 하나다: {rec['check']!r}")

    for i, 보유 in enumerate(rec.get("inventory") or []):
        if not isinstance(보유, dict) or not 보유.get("product_id"):
            문제.append(f"inventory[{i}] 에 product_id 가 없다")
            continue
        사용 = 보유.get("usage_type")
        if 사용 is not None and 사용 not in USAGE_TYPES:
            문제.append(f"inventory[{i}].usage_type 이 알 수 없는 값이다: {사용!r}")

    return 문제


def _상품_id_모으기(rec: dict) -> set[str]:
    ids = {보유["product_id"] for 보유 in (rec.get("inventory") or [])
           if isinstance(보유, dict) and 보유.get("product_id")}
    for 키 in ("expected", "input"):
        값 = rec.get(키)
        if isinstance(값, dict):
            for 목록 in 값.values():
                if isinstance(목록, list):
                    ids.update(v for v in 목록 if isinstance(v, str) and "-" in v and len(v) >= 32)
    return ids


def collect(roots: tuple[Path, ...] = (SYNTHETIC, GOLDEN)) -> tuple[list[str], set[str]]:
    """검사 결과와, 데이터가 참조하는 상품 id 를 돌려준다."""
    문제: list[str] = []
    본_아이디: dict[str, str] = {}
    상품_ids: set[str] = set()

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl")):
            접두어 = _접두어(path)
            if 접두어 is None:
                문제.append(f"{path}: 규칙에 없는 자리다. eval/README.md 의 폴더를 쓴다")
                continue
            골든 = "golden" in path.parts

            for 줄번호, 줄 in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not 줄.strip():
                    continue
                위치 = f"{path.relative_to(AI_ROOT)}:{줄번호}"
                try:
                    rec = json.loads(줄)
                except json.JSONDecodeError as e:
                    문제.append(f"{위치}: JSON 이 아니다 ({e.msg})")
                    continue
                if not isinstance(rec, dict):
                    문제.append(f"{위치}: 한 줄에 객체 하나여야 한다")
                    continue

                for 사유 in _레코드_검사(rec, 접두어, 골든):
                    문제.append(f"{위치}: {사유}")

                아이디 = rec.get("id")
                if isinstance(아이디, str):
                    if 아이디 in 본_아이디:
                        문제.append(f"{위치}: id 가 겹친다 ({본_아이디[아이디]} 에도 있다)")
                    else:
                        본_아이디[아이디] = 위치

                상품_ids |= _상품_id_모으기(rec)

    return 문제, 상품_ids


def _없는_상품(ids: set[str]) -> list[str]:
    """상품 마스터에 실제로 있는지 본다. DB 가 필요해 기본 검사에서 뺐다."""
    if not ids:
        return []
    from db.supabase_client import get_supabase

    sb = get_supabase()
    있는: set[str] = set()
    목록 = sorted(ids)
    for i in range(0, len(목록), 200):
        묶음 = 목록[i:i + 200]
        행 = (sb.table("products").select("product_id")
              .in_("product_id", 묶음).execute()).data or []
        있는 |= {r["product_id"] for r in 행}
    return sorted(ids - 있는)


def main() -> None:
    ap = argparse.ArgumentParser(description="합성 데이터·골든셋 형식 검사")
    ap.add_argument("--db", action="store_true",
                    help="product_id 가 상품 마스터에 있는지까지 본다")
    args = ap.parse_args()

    문제, 상품_ids = collect()

    if args.db:
        for pid in _없는_상품(상품_ids):
            문제.append(f"상품 마스터에 없는 product_id: {pid}")

    if 문제:
        print(f"문제 {len(문제)}건\n")
        for 줄 in 문제:
            print(f"  {줄}")
        sys.exit(1)

    print(f"통과. 상품 id {len(상품_ids)}개를 참조한다.")


if __name__ == "__main__":
    main()
