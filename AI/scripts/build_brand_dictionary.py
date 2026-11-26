"""브랜드 사전 만들기: 글로우픽 카테고리 랭킹 페이지의 브랜드(한글명 · 영문명) + DB 브랜드 + 확인된 별칭.

ProductMatcher v2 가 두 곳에 쓴다.
  1) LLM 이 뽑은 브랜드 표기를 대표 브랜드로 잇는다 (영문 · 한글 · 공식 계정명 아무거나)
  2) LLM 이 브랜드를 못 뽑았으면 캡션 안에 있는 사전 브랜드로 채운다
쇼핑 검색어는 대표 한글명 + 제품명이다 (toocoolforschool → 투쿨포스쿨).

글로우픽은 robots.txt 가 허용하는 경로만 읽는다: 사이트맵(sitemap-categories · sitemap-category3)에 있는 /categories 페이지.
1.5초에 한 번. 페이지 원문은 저장하지 않고 브랜드 객체 {idBrand, name(한글), subName(영문)} 만 추린다.

    cd AI
    python -m scripts.build_brand_dictionary crawl     # 글로우픽 → .cache/glowpick_brands.json (약 10분)
    python -m scripts.build_brand_dictionary build     # 합치기 → data/brand_dictionary.json
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRAWL_OUT = ROOT / ".cache" / "glowpick_brands.json"
DICT_OUT = ROOT / "data" / "brand_dictionary.json"
BASE = "https://www.glowpick.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; hwadam-capstone-research/1.0)"}
DELAY_S = 1.5
SITEMAPS = ("sitemap-categories.xml", "sitemap-category3.xml")


def crawl() -> None:
    import httpx

    from services.master_enricher import _BRAND_OBJ, unescape

    done = json.loads(CRAWL_OUT.read_text(encoding="utf-8")) if CRAWL_OUT.exists() else {"pages": {}, "brands": {}}
    urls = []
    for sm in SITEMAPS:
        r = httpx.get(f"{BASE}/{sm}", headers=UA, timeout=60, follow_redirects=True)
        urls += [u.replace("&amp;", "&") for u in re.findall(r"<loc>([^<]+)</loc>", r.text)]
        time.sleep(DELAY_S)
    paths = [u.replace(BASE, "") for u in urls if "/categories/" in u]
    assert not any(p.startswith(("/searches", "/api")) for p in paths)
    done.setdefault("pages_v2", {})
    todo = [p for p in paths if p not in done["pages_v2"]]     # v2: 랭킹 목록 표시명까지 읽는 두 번째 수집
    print(f"카테고리 페이지 {len(paths)}개, 남은 것 {len(todo)}개")
    for n, p in enumerate(todo, 1):
        try:
            r = httpx.get(BASE + p, headers=UA, timeout=60, follow_redirects=True)
            text = r.text if r.status_code == 200 else ""
        except httpx.HTTPError as e:
            print(f"  실패 {p}: {e}")
            text = ""
        u = unescape(unescape(text)) if text else ""
        objs = _BRAND_OBJ.findall(u) if u else []
        # 브랜드 객체에 이름이 빈 경우가 많다(2,184개 중 665개만 이름). 랭킹 목록의 "N위 브랜드명 | 제품명" 과
        # 상품 JSON 의 idProduct → idBrand 를 이어 브랜드 표시명을 채운다
        p2b = dict(re.findall(r'"idProduct":(\d+),"idBrand":(\d+)', u))
        for _, shown, _, pid in re.findall(r'"name":"(\d+)위 ([^"]+?) \| ([^"]+)","image":"[^"]*","url":"https://www\.glowpick\.com/products/(\d+)"', u):
            if pid in p2b:
                objs.append((p2b[pid], shown, ""))
        for bid, ko, en in objs:
            if int(bid) <= 0:
                continue
            b = done["brands"].setdefault(bid, {"ko": "", "en": "", "seen": 0})
            b["ko"] = b["ko"] or ko.strip()
            b["en"] = b["en"] or en.strip()
            b["seen"] += 1
        done["pages"][p] = len(objs)
        done["pages_v2"][p] = len(objs)
        if n % 20 == 0 or n == len(todo):
            CRAWL_OUT.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  {n}/{len(todo)} · 브랜드 {len(done['brands'])}")
        time.sleep(DELAY_S)


def _key(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def build() -> None:
    from db.supabase_client import get_supabase
    from rules.product_match import load_brand_aliases
    from scripts.evaluate_product_match_v1 import _owned_brands

    gp = json.loads(CRAWL_OUT.read_text(encoding="utf-8"))["brands"] if CRAWL_OUT.exists() else {}
    db_brands = sorted({p["brand"] for p in get_supabase().table("products").select("brand").execute().data or [] if p.get("brand")})
    aliases = load_brand_aliases()                                       # 사람이 확인한 표기 (verified_by 무관, 기존 파일)
    translit = load_brand_aliases(ROOT / "data" / "brand_names_ko.json")  # 제가 음역한 표기 (사람 검토 전)

    entries: list[dict] = []
    by_key: dict[str, dict] = {}

    def index(e: dict, surface: str):
        k = _key(surface)
        if len(k) >= 2 or re.fullmatch(r"[가-힣]", k):
            by_key.setdefault(k, e)
            if surface and surface not in e["aliases"]:
                e["aliases"].append(surface)

    # 1) 글로우픽 브랜드: 한글명 · 영문명. 같은 브랜드 번호는 하나
    for bid, b in sorted(gp.items(), key=lambda kv: -kv[1]["seen"]):
        if not (b["ko"] or b["en"]):
            continue
        e = {"ko": b["ko"] or None, "en": b["en"] or None, "db_brand": None, "glowpick_id": int(bid), "seen": b["seen"],
             "aliases": [], "sources": ["glowpick"]}
        if _key(e["ko"] or "") in by_key or _key(e["en"] or "") in by_key:
            continue  # 같은 표기를 가진 브랜드가 이미 있다 (더 자주 보인 쪽을 남긴다)
        entries.append(e)
        for s in (b["ko"], b["en"]):
            if s:
                index(e, s)

    # 2) DB 브랜드: 글로우픽 표기와 같으면 그 항목에 잇고, 없으면 새 항목
    for db in db_brands:
        cands = [db] + sorted(aliases.get(db, set())) + sorted(translit.get(db, set()))
        e = next((by_key[_key(c)] for c in cands if _key(c) in by_key), None)
        if e is None:
            e = {"ko": None, "en": db, "db_brand": db, "glowpick_id": None, "seen": 0, "aliases": [], "sources": ["db"]}
            entries.append(e)
        e["db_brand"] = e["db_brand"] or db
        if "db" not in e["sources"]:
            e["sources"].append("db")
        index(e, db)
        for a in sorted(aliases.get(db, set())):
            index(e, a)
        for a in sorted(translit.get(db, set())):
            index(e, a)
            if e["ko"] is None and re.search(r"[가-힣]", a):
                e["ko"] = a
                e["sources"].append("translit")

    # 3) 인플루언서 계정의 운영 브랜드 (첫 표기가 대표)
    for names in _owned_brands().values():
        if not names:
            continue
        e = next((by_key[_key(n)] for n in names if _key(n) in by_key), None)
        if e is None:
            ko = next((n for n in names if re.search(r"[가-힣]", n)), None)
            e = {"ko": ko, "en": next((n for n in names if not re.search(r"[가-힣]", n)), None), "db_brand": None,
                 "glowpick_id": None, "seen": 0, "aliases": [], "sources": ["owned"]}
            entries.append(e)
        for n in names:
            index(e, n)

    # 한글명이 비었으면 한글 별칭으로 (확인된 별칭 → 음역 순서는 위에서 넣은 순서)
    for e in entries:
        if not e["ko"]:
            e["ko"] = next((a for a in e["aliases"] if re.search(r"[가-힣]", a)), None)
    # 영문명은 공백 · 기호를 뗀 표기(공식 계정명 모양)도 넣는다: "too cool for school" → toocoolforschool
    for e in entries:
        if e["en"]:
            index(e, re.sub(r"[^0-9A-Za-z]", "", e["en"]))
    DICT_OUT.write_text(json.dumps({"version": "brand-dict-v1", "count": len(entries), "entries": entries},
                                   ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    c = Counter(tuple(sorted(e["sources"])) for e in entries)
    print(f"브랜드 {len(entries)}개 → {DICT_OUT}")
    print("출처별", dict(c))
    print("한글명 없음", sum(1 for e in entries if not e["ko"]), "· DB 브랜드인데 글로우픽에 없음",
          sum(1 for e in entries if e["db_brand"] and not e["glowpick_id"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crawl", "build"])
    args = ap.parse_args()
    crawl() if args.cmd == "crawl" else build()


if __name__ == "__main__":
    main()
