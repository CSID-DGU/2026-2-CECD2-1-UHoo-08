"""ProductMatcher 후보 검색 실험판 (LLM 없음, 같은 입력이면 같은 결과).

v1.2(rules/product_match.rank_candidates_v12)는 그대로 두고, 후보를 찾는 방식만 설정으로 바꿔 가며
비교하려고 만든 코드다. 운영 경로에는 쓰지 않는다. 실험 결과는 eval/reports/ 의 리포트로 남긴다.

바꿔 보는 것 (SearchConfig)
  brand_filter     hard       확인된 브랜드의 상품만 본다 (v1.2)
                   soft       모든 브랜드를 보되, 확인된 브랜드와 다르면 순위 점수를 깎는다
                   brand_all  hard 와 같은 범위에서, 그 브랜드의 상품을 이름 점수와 상관없이 전부 후보로 둔다
  category_filter  hard       추출한 카테고리와 같은 상품만 본다 (v1.2)
                   soft       다른 카테고리도 보되 순위 점수를 깎는다
  top_k            후보 수 (Recall@K 를 잰다)
  embed_k          이름 점수와 별도로, 상품명 임베딩 유사도 상위 몇 개를 후보에 더하나
  embed_bypass     임베딩으로 들어온 후보는 이름 점수가 60 미만이어도 판정 LLM 에 보여 준다
  verify_k         판정 LLM 에 보여 줄 최대 후보 수

후보 하나에는 어떤 경로로 들어왔는지(via: name · embed · alias · brand_all)를 남긴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from rules.product_match import (
    SCOPE,
    V1_UNKNOWN_BRAND_MIN,
    V1_VERIFY_MIN,
    V12_PARTIAL_SCORE,
    V1Candidate,
    alias_keys,
    canon,
    core_name,
    normalize,
    rank_candidates_v12,
    resolve_brand,
    score_name_v12,
    weak_brand_keys,
)

EXP_VERSION = "match-exp-1"

BRAND_PENALTY = 15.0     # soft: 확인된 브랜드와 다른 상품의 순위 점수에서 뺀다
CATEGORY_PENALTY = 10.0  # soft: 추출한 카테고리와 다른 상품의 순위 점수에서 뺀다
BRAND_ALL_CAP = 40       # brand_all: 한 브랜드에서 후보로 둘 최대 상품 수


@dataclass(frozen=True)
class SearchConfig:
    name: str
    brand_filter: str = "hard"        # hard | soft | brand_all
    category_filter: str = "hard"     # hard | soft
    top_k: int = 5
    embed_k: int = 2
    embed_bypass: bool = False
    verify_k: int = 5

    def __post_init__(self):
        if self.brand_filter not in ("hard", "soft", "brand_all"):
            raise ValueError(f"brand_filter: {self.brand_filter}")
        if self.category_filter not in ("hard", "soft"):
            raise ValueError(f"category_filter: {self.category_filter}")

    @property
    def is_v12(self) -> bool:
        """v1.2 와 똑같은 설정이면 rank_candidates_v12 를 그대로 부른다 (기준선이 어긋나지 않게)."""
        return (self.brand_filter, self.category_filter, self.embed_k, self.embed_bypass) == ("hard", "hard", 2, False)


V12 = SearchConfig("v1.2")


@dataclass
class ExpCandidate(V1Candidate):
    via: list[str] = field(default_factory=list)   # name · embed · alias · brand_all
    rank_score: float = 0.0
    brand_match: bool = True
    category_match: bool = True


def _from_v1(c: V1Candidate, via: list[str]) -> ExpCandidate:
    return ExpCandidate(c.product_id, c.brand, c.name, c.category, c.name_score, c.embed_score, c.search_name,
                        list(c.missing), c.alias, via=via, rank_score=c.name_score)


def _alias_hits(mention: dict, byid: dict, byname: dict, product_aliases: list[dict] | None,
                brand: str | None, embed_scores: dict[str, float]) -> list[ExpCandidate]:
    """rank_candidates_v12 의 별칭 후보와 같은 조건."""
    qc = canon(core_name(mention["product_name"]))
    qraw = re.sub(r"\s+", "", (mention["product_name"] or "").lower())
    out = []
    for a in product_aliases or []:
        p = byid.get(a.get("product_id") or "") or byname.get(a.get("official_name") or "")
        ac = canon(a["alias"])
        araw = re.sub(r"\s+", "", a["alias"].lower())
        hit = (len(ac) >= 3 and ac in qc) or (not ac and len(araw) >= 3 and araw in qraw)
        if p and hit and (brand is None or brand in a.get("brands", [p.get("brand")])):
            out.append(ExpCandidate(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                    100.0, embed_scores.get(p["product_id"], 0.0), a["alias"], [], True,
                                    via=["alias"], rank_score=1000.0))
    return out


def search_candidates(mention: dict, products: list[dict], prefixes: dict[str, set[str]], keys: dict[str, str],
                      embed_scores: dict[str, float] | None, cfg: SearchConfig,
                      weak: dict[str, str] | None = None, brand_aliases: dict[str, set[str]] | None = None,
                      product_aliases: list[dict] | None = None) -> tuple[str | None, list[ExpCandidate]]:
    """언급 하나 → (확인된 브랜드, 후보). 후보는 rank_score 순이고 cfg.top_k 개까지다."""
    embed_scores = embed_scores or {}
    if mention.get("mention_type") != "product" or not mention.get("product_name"):
        return None, []

    if cfg.is_v12:
        brand, cands = rank_candidates_v12(mention, products, prefixes, keys, embed_scores, top_k=cfg.top_k, weak=weak,
                                           brand_aliases=brand_aliases, product_aliases=product_aliases)
        out = []
        for c in cands:
            via = ["alias"] if c.alias else (["name"] if c.name_score >= V1_VERIFY_MIN or not c.embed_score else ["embed"])
            out.append(_from_v1(c, via))
        return brand, out

    cat = mention.get("category")
    keys = alias_keys(keys, brand_aliases)
    if weak is None:
        weak = weak_brand_keys(products)
    brand = resolve_brand(mention.get("brand"), keys, weak)
    unknown_brand = False
    if mention.get("brand") and brand is None:
        brand = resolve_brand(mention.get("product_name"), keys)
        unknown_brand = brand is None
    pre = {b: set(ws) for b, ws in prefixes.items()}
    for w, b in weak.items():
        pre.setdefault(b, set()).add(w)
    for b, names in (brand_aliases or {}).items():
        pre.setdefault(b, set()).update(normalize(n) for n in names)
    byid = {p["product_id"]: p for p in products}
    byname = {p.get("name"): p for p in products}
    aliased = _alias_hits(mention, byid, byname, product_aliases, brand, embed_scores)

    other = cat not in SCOPE
    soft_brand = cfg.brand_filter == "soft"
    soft_cat = cfg.category_filter == "soft"

    def in_pool(p: dict) -> bool:
        if not soft_brand and brand is not None and p.get("brand") != brand:
            return False
        if not soft_cat and not other and p.get("category") != cat:
            return False
        return True

    # v1.2 는 브랜드 · 카테고리를 모를 때 후보를 아예 두지 않거나 90점 이상만 둔다. soft 에서도
    # 브랜드를 모르고 카테고리도 범위 밖이면 근거가 이름뿐이라 같은 90점 바닥을 둔다
    pool = [] if (other and brand is None and not soft_cat) else [p for p in products if in_pool(p)]
    scored: list[ExpCandidate] = []
    for p in pool:
        s, sname, miss = score_name_v12(mention["product_name"], p, pre)
        bm = brand is None or p.get("brand") == brand
        cm = other or p.get("category") == cat
        rank = s - (0 if bm else BRAND_PENALTY) - (0 if cm else CATEGORY_PENALTY)
        scored.append(ExpCandidate(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                   s, embed_scores.get(p["product_id"], 0.0), sname, miss, False,
                                   via=["name"], rank_score=rank, brand_match=bm, category_match=cm))

    # 부분 이름 보정: 추출명 단어를 모두 가진 상품이 그 브랜드에 하나뿐이면 90점 (v1.2 와 같다)
    if brand and not other:
        toks = [canon(w) for w in core_name(mention["product_name"]).split() if canon(w)]
        holders = [c for c in scored if c.brand == brand and toks and all(t in canon(c.name) for t in toks)]
        if len(holders) == 1 and holders[0].name_score < V12_PARTIAL_SCORE:
            gap = V12_PARTIAL_SCORE - holders[0].name_score
            holders[0].name_score = float(V12_PARTIAL_SCORE)
            holders[0].rank_score += gap

    # v1.2 의 90점 바닥: 브랜드를 모르거나 카테고리가 범위 밖이면 이름이 거의 같은 상품만 둔다.
    # 그 조건을 풀어 보는 설정(soft)에서만 바닥을 뺀다. 다른 설정은 v1.2 와 같아야 비교가 된다
    floor = (unknown_brand and not soft_brand) or (other and not soft_cat)
    if floor:
        scored = [c for c in scored if c.name_score >= V1_UNKNOWN_BRAND_MIN]

    by_name = sorted(scored, key=lambda c: (-c.rank_score, -c.embed_score))[:cfg.top_k]
    picked = {c.product_id: c for c in by_name}
    if cfg.embed_k and not floor:
        for c in sorted((c for c in scored if c.embed_score > 0), key=lambda c: -c.embed_score)[:cfg.embed_k]:
            if c.product_id in picked:
                if "embed" not in picked[c.product_id].via:
                    picked[c.product_id].via.append("embed")
            else:
                picked[c.product_id] = replace(c, via=["embed"])
    if cfg.brand_filter == "brand_all" and brand:
        for c in sorted((c for c in scored if c.brand == brand), key=lambda c: -c.rank_score)[:BRAND_ALL_CAP]:
            if c.product_id in picked:
                if "brand_all" not in picked[c.product_id].via:
                    picked[c.product_id].via.append("brand_all")
            else:
                picked[c.product_id] = replace(c, via=["brand_all"])

    merged = sorted(picked.values(), key=lambda c: (-c.rank_score, -c.embed_score))
    seen = {c.product_id for c in aliased}
    out = aliased + [c for c in merged if c.product_id not in seen]
    limit = cfg.top_k + (cfg.embed_k if cfg.embed_k else 0)
    if cfg.brand_filter == "brand_all" and brand:
        limit = max(limit, BRAND_ALL_CAP)
    return (brand or (aliased[0].brand if aliased else None)), out[:limit]


def verify_pool_exp(cands: list[ExpCandidate], cfg: SearchConfig) -> list[ExpCandidate]:
    """판정 LLM 에 보여 줄 후보.

    v1.2 는 이름 점수 60 미만을 모두 뺀다(verify_pool). 실험판은 임베딩 경로(embed_bypass) ·
    브랜드 전체 경로(brand_all)로 들어온 후보를 그 바닥 아래여도 남긴다. 순서는 검색 순위 그대로다.
    """
    keep = []
    for c in cands:
        if c.name_score >= V1_VERIFY_MIN or c.alias:
            keep.append(c)
        elif cfg.embed_bypass and "embed" in c.via:
            keep.append(c)
        elif cfg.brand_filter == "brand_all" and "brand_all" in c.via:
            keep.append(c)
    return keep[:max(cfg.verify_k, 1)]
