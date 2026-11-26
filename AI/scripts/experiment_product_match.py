"""ProductMatcher 실패 원인 분석 · 후보 검색 방식 비교 실험 (read-only).

DB 는 읽기만 한다. products · influencer_post_products 에 쓰지 않는다. v0.1 / v1 / v1.2 코드는 고치지 않고
rules/candidate_search 의 설정만 바꿔 같은 235개 게시물(10/29 수집분, 개발셋)을 다시 돌린다.

    cd AI
    python -m scripts.experiment_product_match run              # 매처 실행 (판정 LLM 호출, 캐시함)
    python -m scripts.experiment_product_match labels           # 검수 페이지용 데이터
    python -m scripts.experiment_product_match golden --labels-dir <폴더>   # 검수 완료 라벨 → 골든셋
    python -m scripts.experiment_product_match evaluate         # 골든셋으로 지표 계산

마스터 두 벌
  now   지금 DB 의 상품 전체
  old   14% 를 잰 시점(2026-11-03 오후 확충 전)의 마스터. 지금 상품에서 2026-11-03 06~07시(UTC)에
        등록된 58개를 뺀다. 그 시각 last_updated_at 을 가진 상품이 정확히 그때 등록한 22 + 36 개다

결과는 AI/.cache/match_exp/ 에 둔다(git 에 올리지 않는다). 리포트는 eval/reports/ 에 사람이 쓴다.
정답은 사람이 검수한 골든셋(eval/golden/trend/product_match_v2.jsonl)에서만 온다.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from prompts.product_extract import EXTRACT_VERSION, VERIFY_SYSTEM, VERIFY_VERSION, build_verify_user
from rules.candidate_search import EXP_VERSION, V12, SearchConfig, search_candidates
from rules.match_failure import Row, evaluate
from rules.product_match import (MATCHED, REVIEW, accept_choice_v1_1, auto_decide, brand_keys, brand_prefixes,
                                 load_brand_aliases, load_product_aliases, rank_candidates, verify_pool)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "match_exp"
GOLDEN = ROOT / "eval" / "golden" / "trend" / "product_match_v2.jsonl"
SCOPE = ("base", "sun", "lip", "skincare")
DEV_COLLECTED = "2026-10-29"
OLD_MASTER_ADDED = ("2026-11-03T06", "2026-11-03T07")
CONCURRENCY = 4
VERIFY_TIMEOUT_S = 60.0
PRICE_IN, PRICE_OUT = 0.4, 1.2   # qwen-plus 국제 요금 (USD / 100만 토큰). 청구서로 확인할 것

# 판정까지 돌리는 설정. legacy-v1.1 은 14% 를 낸 조합(v1 후보 검색 + v1.1 인정 규칙)을 다시 돌린 것이다
CONFIGS = [
    SearchConfig("v1.2"),
    SearchConfig("soft", brand_filter="soft", category_filter="soft"),
    SearchConfig("embed", embed_k=3, embed_bypass=True, verify_k=8),
    SearchConfig("brand-all", brand_filter="brand_all", verify_k=20),
    SearchConfig("soft+embed", brand_filter="soft", category_filter="soft", embed_k=3, embed_bypass=True, verify_k=8),
]
LEGACY = "legacy-v1.1"
# 후보 Recall@K 만 재는 검색 방식 (LLM 없음)
RECALL_FAMILIES = {
    "v1.2": dict(),
    "soft": dict(brand_filter="soft", category_filter="soft"),
    "embed": dict(embed_k=3, embed_bypass=True),
    "brand-all": dict(brand_filter="brand_all"),
}
RECALL_KS = (1, 5, 10, 20)


# ── 입력 ──────────────────────────────────────────────────────

def load_inputs() -> dict:
    from db.supabase_client import get_supabase
    from scripts.evaluate_product_match_v1 import _owned_brands

    sb = get_supabase()
    allp = sb.table("products").select("product_id,brand,name,category,last_updated_at").execute().data or []
    now = [p for p in allp if p.get("category") in SCOPE]
    added = {p["product_id"] for p in now if (p.get("last_updated_at") or "").startswith(OLD_MASTER_ADDED)}
    old = [p for p in now if p["product_id"] not in added]
    accounts = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id,username").execute().data or []}
    posts = sb.table("influencer_posts").select("id,account_id,caption,posted_at,collected_at").order("id").execute().data or []
    posts = [p for p in posts if (p.get("collected_at") or "").startswith(DEV_COLLECTED)]
    for p in posts:
        p["username"] = accounts.get(p["account_id"], "")
    return {"masters": {"now": now, "old": old}, "added_after_old": sorted(added), "posts": posts, "owned": _owned_brands()}


def aliases() -> tuple[dict, list[dict]]:
    """브랜드 표기는 전부, 제품 별칭은 사람이 확인한 것만 (나머지는 개발셋에 맞춰 손으로 넣은 것이라 뺀다)."""
    return load_brand_aliases(), [a for a in load_product_aliases() if a.get("verified_by") == "user"]


# ── 판정 LLM: 같은 프롬프트는 캐시, 호출마다 토큰을 센다 ──────────────

class VerifyCache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.data[row["key"]] = row
        self.lock = asyncio.Lock()

    async def call(self, caption: str, mention: dict, cands: list[dict], stats: Counter):
        from services.llm.client import LLMClient, LLMRole, _설정

        user = build_verify_user(caption, mention, cands)
        key = hashlib.sha1(f"{VERIFY_VERSION}\n{VERIFY_SYSTEM}\n{user}".encode("utf-8")).hexdigest()
        hit = self.data.get(key)
        if hit is None:
            client = LLMClient(*_설정(LLMRole.MATCH))   # 호출 하나에 클라이언트 하나: 동시에 돌아도 토큰이 섞이지 않는다
            result = await client.chat_json(system=VERIFY_SYSTEM, user=user, timeout=VERIFY_TIMEOUT_S)
            hit = {"key": key, "result": result, **{k: client.usage[k] for k in ("prompt_tokens", "completion_tokens")}}
            async with self.lock:
                self.data[key] = hit
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(hit, ensure_ascii=False) + "\n")
            stats["fresh_calls"] += 1
        stats["calls"] += 1
        stats["prompt_tokens"] += hit["prompt_tokens"]
        stats["completion_tokens"] += hit["completion_tokens"]
        return hit["result"]


# ── 실행 ──────────────────────────────────────────────────────

async def _legacy_post(post, products, prefixes, keys, llm, cache, owned, search, brand_al, vcache, stats):
    """14% 를 낸 조합: v1 후보 검색(rank_candidates) + 판정 LLM + v1.1 인정 규칙. 제품 별칭 없음."""
    from services.product_extractor import extract_post

    ext = await extract_post(post, llm, cache, owned)
    ms = ext["mentions"]
    embeds = search([f"{m.get('brand') or ''} {m.get('product_name') or ''}".strip() for m in ms]) if ms else []
    rows = []
    for m, emb in zip(ms, embeds):
        brand, cands = rank_candidates(m, products, prefixes, keys, emb)
        status, pid, reason = auto_decide(m, brand, cands)
        method, choice, pool, blocked = ("rule" if status == MATCHED else None), None, [], None
        if status == "verify":
            pool = verify_pool(cands)
            result = await vcache.call(post.get("caption") or "", m, [asdict(c) for c in pool], stats)
            choice = result.get("choice") if isinstance(result, dict) else None
            method = "llm"
            status, pid, reason = accept_choice_v1_1(choice, pool, m, brand_al)
            if status == REVIEW and any(c.product_id == choice for c in pool):
                blocked = reason
        rows.append({"config": LEGACY, "mention": m, "brand_resolved": brand, "status": status, "product_id": pid,
                     "method": method, "reason": reason, "candidates": [asdict(c) for c in cands],
                     "pool": [c.product_id for c in pool], "llm_choice": choice, "blocked": blocked})
    return {"extract": ext, "rows": rows}


async def run_all(inp: dict, master_names: list[str], config_names: list[str]) -> None:
    from scripts.evaluate_product_match import link_handles
    from services.embedding_service import EmbeddingService
    from services.llm import LLMRole, get_llm
    from services.product_extractor import ExtractCache
    from services.product_matcher_exp import match_post_exp
    from services.product_matcher_v1 import make_name_index

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runs").mkdir(exist_ok=True)
    llm = get_llm(LLMRole.MATCH)
    cache = ExtractCache()
    vcache = VerifyCache(OUT / "verify_cache.jsonl")
    brand_al, prod_al = aliases()
    emb = EmbeddingService.get()
    search = make_name_index(inp["masters"]["now"], emb.embed_batch)   # old 는 now 의 부분집합이라 같은 색인을 쓴다
    posts = inp["posts"]
    summary = json.loads((OUT / "runs" / "summary.json").read_text(encoding="utf-8")) if (OUT / "runs" / "summary.json").exists() else {}

    for mname in master_names:
        products = inp["masters"][mname]
        prefixes = brand_prefixes(products)
        keys = brand_keys(products, prefixes, link_handles(products, posts)[0])
        for cname in config_names:
            cfg = next((c for c in CONFIGS if c.name == cname), None)
            stats = Counter()
            sem = asyncio.Semaphore(CONCURRENCY)

            async def vfn(caption, m, cands, stats=stats):
                return await vcache.call(caption, m, cands, stats)

            async def one(p, cfg=cfg, stats=stats, products=products, prefixes=prefixes, keys=keys):
                async with sem:
                    if cname == LEGACY:
                        res = await _legacy_post(p, products, prefixes, keys, llm, cache, inp["owned"].get(p["username"]),
                                                 search, brand_al, vcache, stats)
                    else:
                        res = await match_post_exp(p, products, prefixes, keys, llm, cfg, vfn, cache,
                                                   inp["owned"].get(p["username"]), search, brand_al, prod_al)
                    return {"post_id": p["id"], "extract_cached": res["extract"].get("cached"),
                            "extract_failed": res["extract"]["failed"], "rows": res["rows"]}

            t0 = time.perf_counter()
            results = await asyncio.gather(*(one(p) for p in posts))
            elapsed = time.perf_counter() - t0
            path = OUT / "runs" / f"{mname}__{cname}.jsonl"
            with path.open("w", encoding="utf-8", newline="\n") as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            rows = [x for r in results for x in r["rows"]]
            prod = [x for x in rows if x["mention"]["mention_type"] == "product"]
            summary[f"{mname}__{cname}"] = {
                "master": mname, "config": cname, "products": len(products), "posts": len(posts),
                "extract_not_cached": sum(1 for r in results if r["extract_cached"] is False),
                "extract_failed": sum(r["extract_failed"] for r in results),
                "mentions": dict(Counter(x["mention"]["mention_type"] for x in rows)),
                "status_product_mentions": dict(Counter(x["status"] for x in prod)),
                "method_matched": dict(Counter(x["method"] for x in prod if x["status"] == MATCHED)),
                # 시스템 기준(검수 전): matched 를 낸 product 언급 / product 언급. 정확도가 아니다
                "system_match_rate_unverified": round(sum(x["status"] == MATCHED for x in prod) / len(prod), 4) if prod else None,
                "blocked": sum(1 for x in rows if x["blocked"]),
                "verify_calls": stats["calls"], "verify_fresh_calls": stats["fresh_calls"],
                "prompt_tokens": stats["prompt_tokens"], "completion_tokens": stats["completion_tokens"],
                "cost_usd_est": round(stats["prompt_tokens"] / 1e6 * PRICE_IN + stats["completion_tokens"] / 1e6 * PRICE_OUT, 4),
                "elapsed_s": round(elapsed, 1),
                "versions": {"exp": EXP_VERSION, "extract": EXTRACT_VERSION, "verify": VERIFY_VERSION},
            }
            print(json.dumps(summary[f"{mname}__{cname}"], ensure_ascii=False))
            (OUT / "runs" / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

        # 후보 Recall@K 용 검색만 (LLM 없음). 추출은 캐시에서 꺼낸다
        rec = {}
        exts = {p["id"]: cache.get(_ext_key(p)) for p in posts}
        embeds = {}
        for p in posts:
            ms = (exts[p["id"]] or {}).get("mentions", [])
            embeds[p["id"]] = search([f"{m.get('brand') or ''} {m.get('product_name') or ''}".strip() for m in ms]) if ms else []
        for fam, kw in RECALL_FAMILIES.items():
            for k in RECALL_KS:
                cfg = SearchConfig(f"{fam}@{k}", top_k=k, **kw)
                rec[cfg.name] = {str(p["id"]): [{"t": m["mention_type"],
                                                 "c": [c.product_id for c in search_candidates(m, products, prefixes, keys, e, cfg,
                                                                                               brand_aliases=brand_al,
                                                                                               product_aliases=prod_al)[1]]}
                                                for m, e in zip((exts[p["id"]] or {}).get("mentions", []), embeds[p["id"]])]
                                 for p in posts}
        (OUT / "runs" / f"{mname}__recall_candidates.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    meta = {"added_after_old": inp["added_after_old"], "posts": [p["id"] for p in posts],
            "masters": {k: len(v) for k, v in inp["masters"].items()}}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _ext_key(p: dict) -> str:
    from services.product_extractor import cache_key
    return cache_key(p["id"], p.get("caption") or "")


# ── 검수 페이지 데이터 ────────────────────────────────────────

def build_labels(inp: dict) -> None:
    """게시물 · 추출 언급 · 후보 제안(여러 설정의 후보 합집합)을 페이지에 넣을 JSON 으로 낸다.

    제안은 입력을 돕는 것일 뿐 정답이 아니다. 페이지는 아무것도 미리 고르지 않는다.
    """
    runs = {}
    for cname in [c.name for c in CONFIGS]:
        path = OUT / "runs" / f"now__{cname}.jsonl"
        if path.exists():
            runs[cname] = {json.loads(l)["post_id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()}
    added = set(inp["added_after_old"])
    out_posts = []
    for p in inp["posts"]:
        base = runs.get("v1.2", {}).get(p["id"])
        if base is None:
            continue
        ms = []
        for i, r in enumerate(base["rows"]):
            sugg = []
            for cname, rr in runs.items():
                row = rr[p["id"]]["rows"][i]
                for c in row["candidates"][:8]:
                    if c["product_id"] not in sugg:
                        sugg.append(c["product_id"])
                if row["status"] == MATCHED and row["product_id"] and row["product_id"] not in sugg:
                    sugg.insert(0, row["product_id"])
            m = r["mention"]
            ms.append({"i": i, "b": m.get("brand"), "n": m.get("product_name"), "c": m.get("category"), "t": m["mention_type"],
                       "e": m.get("evidence"), "s": sugg[:12],
                       "sys": {cname: (rr[p["id"]]["rows"][i]["status"], rr[p["id"]]["rows"][i]["product_id"]) for cname, rr in runs.items()}})
        out_posts.append({"id": p["id"], "u": p["username"], "d": (p.get("posted_at") or "")[:10], "cap": p.get("caption") or "", "m": ms})
    prods = [{"id": p["product_id"], "b": p.get("brand"), "n": p.get("name"), "c": p.get("category"), "new": p["product_id"] in added}
             for p in inp["masters"]["now"]]
    data = {"version": {"extract": EXTRACT_VERSION, "exp": EXP_VERSION}, "posts": out_posts, "products": prods}
    (OUT / "labels_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"게시물 {len(out_posts)} · 언급 {sum(len(p['m']) for p in out_posts)} · 상품 {len(prods)}")


# ── 검수 라벨 → 골든셋 ────────────────────────────────────────

def build_golden(labels_dir: Path) -> None:
    """검수 페이지에서 '검수 완료'를 누른 게시물만 골든셋 한 줄로 바꾼다.

    labels_dir 는 검수 페이지 저장소(labels 컬렉션)를 문서 하나에 파일 하나로 내려받은 폴더다.
    추출 언급마다 고른 종류를 항목으로 묶는다. 같은 DB 제품을 가리킨 언급은 한 항목이 된다.
    '제품 아님'은 정답 항목이 아니다(추출 오류로만 센다).
    """
    data = json.loads((OUT / "labels_data.json").read_text(encoding="utf-8"))
    posts = {p["id"]: p for p in data["posts"]}
    out, skipped = [], 0
    for f in sorted(labels_dir.glob("*.json"), key=lambda x: int(x.stem) if x.stem.isdigit() else 0):
        body = json.loads(f.read_text(encoding="utf-8"))
        pid = int(f.stem)
        if not body.get("done") or pid not in posts:
            skipped += 1
            continue
        p = posts[pid]
        items: list[dict] = []
        by_pid: dict[str, dict] = {}
        not_product = []
        for k, v in sorted((body.get("mentions") or {}).items(), key=lambda kv: int(kv[0])):
            i = int(k)
            kind = v.get("kind")
            if kind == "not_product":
                not_product.append(i)
            elif kind == "in_db" and v.get("pid"):
                it = by_pid.setdefault(v["pid"], {"kind": "in_db", "product_id": v["pid"], "mentions": []})
                it["mentions"].append(i)
            elif kind in ("not_in_db", "out_of_scope", "not_cosmetic", "unspecific"):
                m = p["m"][i]
                items.append({"kind": kind, "brand": m.get("b"), "name": v.get("name") or m.get("n"), "mentions": [i]})
        for x in body.get("missed") or []:
            if x.get("kind") == "in_db" and x.get("pid"):
                by_pid.setdefault(x["pid"], {"kind": "in_db", "product_id": x["pid"], "mentions": []})
            elif x.get("kind"):
                items.append({"kind": x["kind"], "brand": None, "name": x.get("name"), "mentions": []})
        out.append({
            "id": f"trend-g-m2-{pid:04d}", "split": "dev", "source": "real", "tags": ["product_match"],
            "note": body.get("note") or "", "verified_by": "user", "verified_at": (body.get("updated_at") or "")[:10],
            "input": {"post_id": pid, "username": p["u"], "caption": p["cap"]},
            "expected": {"extract_version": data["version"]["extract"], "items": list(by_pid.values()) + items,
                         "not_product_mentions": not_product},
            "check": "exact",
        })
    with GOLDEN.open("w", encoding="utf-8", newline="\n") as f:
        for g in out:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(f"골든셋 {len(out)}건 (검수 완료 아님 {skipped}건 제외) → {GOLDEN}")


# ── 평가 ──────────────────────────────────────────────────────

def _rows(run_rows: list[dict]) -> list[Row]:
    return [Row(r["mention"]["mention_type"], r["status"], r["product_id"], r["method"],
                [c["product_id"] for c in r["candidates"]], r["pool"], r["llm_choice"]) for r in run_rows]


def run_evaluate() -> None:
    golds = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    golds = [g for g in golds if g.get("verified_by") == "user"]
    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "runs" / "summary.json").read_text(encoding="utf-8"))
    report = {"golden_posts": len(golds), "runs": {}, "recall_at_k": {}, "blocked": {}}
    for key, s in summary.items():
        path = OUT / "runs" / f"{key}.jsonl"
        runs = {json.loads(l)["post_id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()}
        master_ids = None
        if s["master"] == "old":
            added = set(meta["added_after_old"])
            master_ids = _all_ids_minus(added)
        rows_by_post = {pid: _rows(r["rows"]) for pid, r in runs.items()}
        ev = evaluate(golds, rows_by_post, master_ids=master_ids)
        ev["cost"] = {k: s[k] for k in ("verify_calls", "prompt_tokens", "completion_tokens", "cost_usd_est")}
        report["runs"][key] = ev
        # 인정 규칙이 막은 사례: 정답과 비교해 과차단인지 정상 차단인지
        gold_by_post = {g["input"]["post_id"]: g for g in golds}
        bl = []
        for pid, r in runs.items():
            for i, x in enumerate(r["rows"]):
                if not x["blocked"]:
                    continue
                g = gold_by_post.get(pid)
                verdict = "검수 전"
                if g:
                    mine = [it for it in g["expected"]["items"] if i in (it.get("mentions") or [])]
                    if any(it["kind"] == "in_db" and it["product_id"] == x["llm_choice"] for it in mine):
                        verdict = "과차단: LLM 답이 정답"
                    elif mine:
                        verdict = "정상 차단: LLM 답이 오답"
                    else:
                        verdict = "정상 차단: 제품 언급이 아님"
                bl.append({"post_id": pid, "mention": i, "extracted": x["mention"].get("product_name"),
                           "evidence": x["mention"].get("evidence"), "llm_choice": x["llm_choice"],
                           "llm_choice_name": next((c["name"] for c in x["candidates"] if c["product_id"] == x["llm_choice"]), ""),
                           "reason": x["blocked"], "verdict": verdict})
        report["blocked"][key] = bl
    for mname in ("now", "old"):
        path = OUT / "runs" / f"{mname}__recall_candidates.json"
        if not path.exists():
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        master_ids = _all_ids_minus(set(meta["added_after_old"])) if mname == "old" else None
        for name, by_post in rec.items():
            rows_by_post = {int(pid): [Row(x["t"], "unmatched", None, None, x["c"], []) for x in cands]
                            for pid, cands in by_post.items()}
            ev = evaluate(golds, rows_by_post, ks=(int(name.split("@")[1]),), master_ids=master_ids)
            report["recall_at_k"][f"{mname}__{name}"] = ev["candidate_recall"]
    (OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {"recall_in_db": v["recall_in_db"], "precision": v["precision"], "auto_precision": v["auto_precision"],
                          "stages": v["stages"]} for k, v in report["runs"].items()}, ensure_ascii=False, indent=1))


def _all_ids_minus(added: set[str]) -> set[str]:
    from db.supabase_client import get_supabase
    ids = {p["product_id"] for p in get_supabase().table("products").select("product_id").execute().data or []}
    return ids - added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "labels", "golden", "evaluate"])
    ap.add_argument("--labels-dir", help="golden: 검수 페이지 저장소를 내려받은 폴더")
    ap.add_argument("--masters", default="now,old")
    ap.add_argument("--configs", default=",".join([c.name for c in CONFIGS] + [LEGACY]))
    args = ap.parse_args()
    if args.cmd == "evaluate":
        run_evaluate()
        return
    if args.cmd == "golden":
        build_golden(Path(args.labels_dir))
        return
    inp = load_inputs()
    print(f"게시물 {len(inp['posts'])} · 상품 now {len(inp['masters']['now'])} / old {len(inp['masters']['old'])}")
    if args.cmd == "run":
        asyncio.run(run_all(inp, args.masters.split(","), args.configs.split(",")))
    else:
        build_labels(inp)


if __name__ == "__main__":
    main()
