"""ProductMatcher v1 하이브리드 후보 검색과 판정 검사 (LLM 없음, 같은 입력이면 같은 결과).

인플루언서는 공식 제품명과 다르게 부른다. DB 에는 "에스네이처 딥 아쿠아 스쿠알란 베리어 세럼" 이
있는데 캡션에는 "장벽천재세럼" 이라고 적는다. 이름 유사도만으로는 이 둘이 이어지지 않는다.
그래서 후보를 네 가지 신호로 찾고 순위를 합친다(Reciprocal Rank Fusion).

  name     이름 유사도 (RapidFuzz, rules/product_match.score_name)
  embed    제품명 임베딩 코사인 (feature_vec 이 아니라 상품명 전용 임베딩)
  feature  제품 종류(세럼 · 토너 …)와 캡션에 나온 성분이 상품 feature_json 과 맞는 정도
  alias    검증된 별칭 사전(data/product_aliases.json)에 그 표현이 있는가

후보는 브랜드로 먼저 거른다. 브랜드가 확인되지 않으면 이름 · 별칭 근거가 있는 후보만 남긴다.

판정 LLM 의 답은 check_choice 가 다시 본다. 근거 문구가 캡션에 있는지, 제품 종류가 맞는지,
같은 브랜드 · 같은 종류의 다른 후보가 있는데 이름 근거 없이 골랐는지, 후보 이름의 마무리 표현
("매트")이 언급과 어긋나는지. 하나라도 걸리면 review 다. LLM 의 자기보고 확신도는 쓰지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rules.product_match import (
    MATCHED,
    REVIEW,
    SCOPE,
    compact,
    core_name,
    normalize,
    resolve_brand,
    score_name,
    weak_brand_keys,
)

RETRIEVAL_VERSION = "hybrid-v1"
RRF_K = 60
TOP_K = 10
AUTO_NAME = 95          # 규칙 확정: 이름 점수
AUTO_GAP = 8            # 규칙 확정: 1 · 2 위 이름 점수 차
NAME_EVIDENCE = 70      # 이 점수 이상이면 "이름 근거가 있다"
UNKNOWN_BRAND_NAME = 90  # 브랜드 미확인일 때 후보로 남길 이름 점수

# 상품명 · 언급에 나오는 제품 종류 말 → feature_json.product_type 묶음
TYPE_GROUPS = {
    "세럼": "serum", "앰플": "serum", "에센스": "serum", "부스터": "serum",
    "토너": "toner", "스킨": "toner", "미스트": "toner",
    "크림": "cream", "밤": "balm", "로션": "lotion", "에멀전": "lotion", "오일": "oil",
    "쿠션": "cushion", "파운데이션": "foundation", "컨실러": "concealer", "프라이머": "primer", "베이스": "primer",
    "틴트": "tint", "립스틱": "lipstick", "글로스": "gloss", "립글로스": "gloss", "립밤": "balm", "립펜슬": "lipstick",
    "선크림": "sun", "선스틱": "sun", "선쿠션": "sun", "선세럼": "sun", "선에센스": "sun", "선스크린": "sun", "선로션": "sun",
}
# feature_json.product_type 값 → 같은 묶음
PRODUCT_TYPE_GROUP = {
    "세럼": "serum", "에센스": "serum", "앰플": "serum", "토너": "toner", "크림": "cream", "로션": "lotion", "오일": "oil",
    "쿠션": "cushion", "파운데이션": "foundation", "컨실러": "concealer", "프라이머": "primer",
    "틴트": "tint", "립스틱": "lipstick", "립글로스": "gloss", "립밤": "balm",
    "선크림": "sun", "선스틱": "sun", "선쿠션": "sun", "선스프레이": "sun",
}
# 캡션에서 찾는 성분 표기 → key_ingredient 표준명
INGREDIENT_WORDS = {
    "스쿠알란": "스쿠알란", "판테놀": "판테놀", "히알루론": "히알루론산", "히알루로닉": "히알루론산", "세라마이드": "세라마이드",
    "시카": "병풀추출물", "병풀": "병풀추출물", "센텔라": "병풀추출물", "마데카": "병풀추출물", "나이아신": "나이아신아마이드",
    "레티놀": "레티놀", "바쿠치올": "바쿠치올", "콜라겐": "콜라겐", "펩타이드": "펩타이드", "어성초": "어성초", "티트리": "티트리",
    "비타민c": "비타민C", "비타c": "비타민C유도체", "알란토인": "알란토인", "프로폴리스": "프로폴리스", "아데노신": "아데노신",
}
# 후보 이름에 있는데 언급에 없으면 다른 제품일 수 있는 마무리 · 라인 표현
FINISH_WORDS = {"매트", "세미매트", "글로우", "듀이", "벨벳", "새틴", "블러", "톤업", "커버", "워터"}


def mention_type_group(text: str) -> str | None:
    """언급 표현에서 제품 종류 묶음. 긴 말부터 본다("선크림" 이 "크림" 보다 먼저)."""
    t = compact(normalize(text))
    for w in sorted(TYPE_GROUPS, key=len, reverse=True):
        if w in t:
            return TYPE_GROUPS[w]
    return None


def product_type_group(product: dict) -> str | None:
    f = product.get("features") or {}
    g = PRODUCT_TYPE_GROUP.get(f.get("product_type") or "")
    if g:
        return g
    if product.get("category") == "sun":
        return "sun"
    return mention_type_group(product.get("name") or "")


def caption_ingredients(caption: str) -> set[str]:
    t = compact(normalize(caption))
    return {std for w, std in INGREDIENT_WORDS.items() if w in t}


def feature_score(mention_group: str | None, ingredients: set[str], product: dict) -> float:
    """종류가 맞으면 1, 성분이 겹칠 때마다 0.5. 종류가 다르면 0 (성분만으로 다른 종류를 올리지 않는다)."""
    pg = product_type_group(product)
    if mention_group and pg and mention_group != pg:
        return 0.0
    keys = set((product.get("features") or {}).get("key_ingredient") or [])
    return (1.0 if mention_group and pg == mention_group else 0.0) + 0.5 * len(ingredients & keys)


@dataclass
class Alias:
    alias: str
    product_id: str
    verified_by: str = ""


def alias_hits(text: str, aliases: list[Alias]) -> set[str]:
    """언급 표현에 검증된 별칭이 들어 있는 상품들."""
    t = compact(normalize(text))
    return {a.product_id for a in aliases if len(compact(normalize(a.alias))) >= 3 and compact(normalize(a.alias)) in t}


@dataclass
class Hit:
    product_id: str
    brand: str
    name: str
    category: str | None
    product_type: str | None
    key_ingredient: list[str]
    name_score: float = 0.0
    embed_score: float = 0.0
    feature_score: float = 0.0
    alias: bool = False
    rrf: float = 0.0
    ranks: dict = field(default_factory=dict)
    search_name: str = ""
    missing: list[str] = field(default_factory=list)


def _rrf(lists: dict[str, list[str]]) -> dict[str, tuple[float, dict]]:
    out: dict[str, tuple[float, dict]] = {}
    for sig, ids in lists.items():
        for r, pid in enumerate(ids, 1):
            s, ranks = out.get(pid, (0.0, {}))
            ranks[sig] = r
            out[pid] = (s + 1 / (RRF_K + r), ranks)
    return out


def retrieve(mention: dict, caption: str, products: list[dict], prefixes: dict, keys: dict,
             embed_scores: dict[str, float] | None = None, aliases: list[Alias] | None = None,
             signals: tuple[str, ...] = ("name", "embed", "feature", "alias"), top_k: int = TOP_K,
             weak: dict | None = None) -> tuple[str | None, list[Hit]]:
    """언급 하나 → (확인된 브랜드, 후보 TOP k). signals 로 쓸 신호를 고른다(name 만 = RapidFuzz 단독)."""
    if mention.get("mention_type") != "product" or not mention.get("product_name"):
        return None, []
    cat = mention.get("category")
    if cat == "other":
        return None, []
    weak = weak if weak is not None else weak_brand_keys(products)
    brand = resolve_brand(mention.get("brand"), keys, weak) or resolve_brand(mention.get("product_name"), keys)
    unknown = bool(mention.get("brand")) and brand is None
    text = f"{mention.get('brand') or ''} {mention.get('product_name') or ''}"
    pre = {b: set(ws) for b, ws in prefixes.items()}
    for w, b in weak.items():
        pre.setdefault(b, set()).add(w)
    pool = [p for p in products if (brand is None or p.get("brand") == brand) and (cat not in SCOPE or p.get("category") == cat)]
    group = mention_type_group(mention.get("product_name") or "")
    ings = caption_ingredients(caption)
    a_hits = alias_hits(text, aliases or []) if "alias" in signals else set()
    embed_scores = embed_scores or {}

    hits = {}
    for p in pool:
        s, sname, miss = score_name(mention["product_name"], p, pre)
        f = p.get("features") or {}
        hits[p["product_id"]] = Hit(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                    f.get("product_type"), list(f.get("key_ingredient") or []), s,
                                    embed_scores.get(p["product_id"], 0.0) if "embed" in signals else 0.0,
                                    feature_score(group, ings, p) if "feature" in signals else 0.0,
                                    p["product_id"] in a_hits, search_name=sname, missing=miss)
    if unknown:  # 브랜드를 모르면 이름 · 별칭 근거가 있는 후보만
        hits = {k: h for k, h in hits.items() if h.name_score >= UNKNOWN_BRAND_NAME or h.alias}
    lists = {"name": [h.product_id for h in sorted(hits.values(), key=lambda h: -h.name_score) if h.name_score > 0][:top_k * 2]}
    if "embed" in signals:
        lists["embed"] = [h.product_id for h in sorted(hits.values(), key=lambda h: -h.embed_score) if h.embed_score > 0][:top_k * 2]
    if "feature" in signals:
        lists["feature"] = [h.product_id for h in sorted(hits.values(), key=lambda h: -h.feature_score) if h.feature_score > 0][:top_k * 2]
    if "alias" in signals:
        lists["alias"] = [pid for pid in hits if hits[pid].alias]
    fused = _rrf(lists)
    for pid, (score, ranks) in fused.items():
        hits[pid].rrf, hits[pid].ranks = score + (1.0 if hits[pid].alias else 0.0), ranks
    ranked = sorted((h for h in hits.values() if h.product_id in fused), key=lambda h: (-h.rrf, -h.name_score))
    return brand, ranked[:top_k]


def auto_decide(mention: dict, brand: str | None, hits: list[Hit]) -> tuple[str, str | None, str]:
    """규칙으로 정할 수 있는 것만 정한다. (status, product_id, 사유). 나머지는 resolve(판정 LLM)."""
    mt = mention.get("mention_type")
    if mt in ("brand_only", "category_only"):
        return mt, None, "제품을 특정할 수 없는 언급"
    if not hits:
        return "unmatched", None, "후보 없음"
    aliased = [h for h in hits if h.alias]
    if brand and len(aliased) == 1 and aliased[0].brand == brand:
        return MATCHED, aliased[0].product_id, "검증된 별칭"
    by_name = sorted(hits, key=lambda h: -h.name_score)
    top, second = by_name[0], (by_name[1].name_score if len(by_name) > 1 else 0.0)
    if brand and top.brand == brand and top.name_score >= AUTO_NAME and top.name_score - second >= AUTO_GAP and not top.missing:
        return MATCHED, top.product_id, "규칙 확정: 브랜드 일치 · 이름 일치"
    return "resolve", None, "판정 LLM 에 넘김"


def _squash(t: str) -> str:
    return re.sub(r"\s+", "", (t or "").lower())


def check_choice(answer: object, mention: dict, brand: str | None, hits: list[Hit], caption: str) -> tuple[str, str | None, str]:
    """판정 LLM 의 답을 규칙으로 다시 본다. (status, product_id, 사유)."""
    if not isinstance(answer, dict):
        return REVIEW, None, "판정 응답을 읽지 못함"
    choice = answer.get("choice")
    if choice in ("review", "unmatched"):
        return choice, None, str(answer.get("reason") or "")
    picked = next((h for h in hits if h.product_id == choice), None)
    if picked is None:
        return REVIEW, None, f"후보 밖의 답 {choice!r}"
    evidence = answer.get("evidence") if isinstance(answer.get("evidence"), list) else []
    evidence = [e for e in evidence if isinstance(e, str) and e.strip()]
    if not evidence or not all(_squash(e) in _squash(caption) for e in evidence):
        return REVIEW, None, "근거 문구가 캡션에 없음"
    group = mention_type_group(mention.get("product_name") or "")
    pg = product_type_group({"features": {"product_type": picked.product_type}, "category": picked.category, "name": picked.name})
    if group and pg and group != pg:
        return REVIEW, None, f"제품 종류가 다름 ({group} ↔ {pg})"
    name_evidence = picked.name_score >= NAME_EVIDENCE or picked.alias
    if brand is None and not name_evidence:
        return REVIEW, None, "브랜드 미확인 · 이름 근거 없음"
    rivals = [h for h in hits if h is not picked and h.brand == picked.brand
              and product_type_group({"features": {"product_type": h.product_type}, "category": h.category, "name": h.name}) == pg]
    if rivals and not name_evidence:
        return REVIEW, None, "같은 브랜드 · 같은 종류 후보가 여럿: " + ", ".join(h.name for h in rivals[:3])
    said = compact(normalize(f"{mention.get('product_name') or ''} {mention.get('variant') or ''}"))
    clash = [w for w in FINISH_WORDS if w in normalize(picked.name).split() and w not in said]
    if clash:
        return REVIEW, None, "후보 이름의 마무리 표현이 언급에 없음: " + ", ".join(clash)
    return MATCHED, picked.product_id, str(answer.get("reason") or "")
