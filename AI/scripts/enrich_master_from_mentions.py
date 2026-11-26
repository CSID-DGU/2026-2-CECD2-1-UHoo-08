"""매칭 실패 언급 → 마스터 확충 에이전트(services/master_enricher) → 등록 후보 파일. DB 에 쓰지 않는다.

    cd AI
    python -m scripts.enrich_master_from_mentions --rows <평가 결과 폴더>/rows.csv --posts-file <게시물 JSON> \
        --catalog <글로우픽 랭킹 목록 JSON> --brand-ids <브랜드 번호 JSON> --out <폴더>

결과
  candidates.json      언급마다 에이전트 결과 (found · no_brand · no_product)
  extra_products.json  찾은 제품을 상품 마스터 모양으로 (평가 스크립트 --extra-products 로 메모리에서만 더한다)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--posts-file")
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--brand-ids", required=True)
    ap.add_argument("--cache", default=".cache/glowpick")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    from rules.product_match import alias_keys, brand_keys, brand_prefixes, load_brand_aliases, resolve_brand, weak_brand_keys
    from scripts.evaluate_product_match_v1 import _load
    from services.master_enricher import Glowpick, MasterEnricher

    products, posts = _load()
    if args.posts_file:
        raw = json.loads(Path(args.posts_file).read_text(encoding="utf-8"))
        posts = [{"id": 100000 + i, "caption": r.get("caption") or ""} for i, r in enumerate(raw)]
    caps = {str(p["id"]): p.get("caption") or "" for p in posts}
    aliases = load_brand_aliases()
    keys = alias_keys(brand_keys(products, brand_prefixes(products)), aliases)
    weak = weak_brand_keys(products)
    llm = None
    if not args.no_llm:
        from services.llm import LLMRole, get_llm
        llm = get_llm(LLMRole.MATCH)
    from services.master_enricher import brand_index
    # 브랜드 번호: 받아 둔 글로우픽 페이지에서 자동으로 만든 색인 + 확인된 표
    ids = brand_index(f.read_text(encoding="utf-8") for f in Path(args.cache).glob("*.html"))
    ids.update(json.loads(Path(args.brand_ids).read_text(encoding="utf-8")))
    en = MasterEnricher(Glowpick(Path(args.cache)), ids,
                        json.loads(Path(args.catalog).read_text(encoding="utf-8")), aliases, llm)
    rows = [r for r in csv.DictReader(open(args.rows, encoding="utf-8-sig"))
            if r["mention_type"] == "product" and r.get("status_v1_1", r["status"]) != "matched"]

    async def run():
        out = []
        for r in rows:
            m = {"brand": r["brand"], "product_name": r["extracted"], "category": r["category"], "mention_type": "product",
                 "evidence": r["evidence"], "specificity": r["specificity"]}
            db_brand = resolve_brand(r["brand"], keys, weak) or resolve_brand(r["extracted"], keys)
            try:
                res = await en.resolve(m, db_brand, caps.get(r["post_id"], ""))
            except Exception as e:  # 실험 스크립트: 언급 하나의 실패는 기록하고 넘어간다
                res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
            out.append({"post_id": r["post_id"], "mention": m, "db_brand": db_brand, **res})
            print(r["post_id"], r["brand"], r["extracted"][:24], "→", res["status"], (res.get("candidate") or {}).get("name", res.get("best", "")), flush=True)
        return out

    out = asyncio.run(run())
    od = Path(args.out); od.mkdir(parents=True, exist_ok=True)
    (od / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    extra = {}
    for x in out:
        c = x.get("candidate")
        if c:
            extra[c["glow_id"]] = {"product_id": f"glow-{c['glow_id']}", "brand": c["db_brand"], "name": c["name"],
                                   "category": c["category"]}
    (od / "extra_products.json").write_text(json.dumps(list(extra.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(Counter(x["status"] for x in out), "products", len(extra), "requests", en.gp.requests)


if __name__ == "__main__":
    main()
