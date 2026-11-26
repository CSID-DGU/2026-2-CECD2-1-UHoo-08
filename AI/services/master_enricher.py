"""마스터 확충 에이전트: 매칭에 실패한 제품 언급 → 글로우픽에서 같은 제품 찾기 → 등록 후보.

매칭 실패의 대부분은 마스터에 그 제품이 없어서다(2026-11-03, DB 밖 게시물 410개 평가). 사람이 하던
"브랜드 페이지에서 그 제품을 찾아 정보를 옮겨 적기"를 에이전트가 한다. DB 에 쓰지 않는다. 등록 후보를
돌려주고, 등록은 사람이 확인한 뒤 따로 한다.

글로우픽은 robots.txt 가 허용하는 경로만 읽는다: /categories/{n} · /brands/{id} · /products/{id}(/details).
검색(/searches)은 막혀 있어 쓰지 않는다. 1.5초에 한 번, 받은 페이지는 캐시한다.

브랜드 찾기
  1) 확인된 브랜드 번호 표(brand_ids) 2) 카테고리 랭킹 목록(catalog)에 같은 한글 브랜드명 상품이 있으면
  그 상품 페이지의 브랜드 링크 3) 없으면 그 브랜드는 못 찾음(no_brand)
제품 찾기
  브랜드 페이지(전체 · 분류별)의 상품을 score_name_v12 로 비교한다. 100점(정규형 일치)은 바로 후보,
  90점(부분 이름 · 호수명)은 판정 LLM 에 넘겨 accept_choice_v1_2 로 다시 본다. 그 아래는 못 찾음.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from rules.product_match import (
    MATCHED,
    V12_PARTIAL_SCORE,
    V1Candidate,
    accept_choice_v1_2,
    canon,
    score_name_v12,
)

BASE = "https://www.glowpick.com"
CATE1 = [None, 1, 2, 3, 9]       # 전체 · 스킨케어 · 베이스 · 립 · 선케어
SCOPE = {"base", "sun", "lip", "skincare"}
BS = chr(92)


def unescape(html: str) -> str:
    return (html or "").replace(BS + '"', '"').replace(BS + BS, BS)


def brand_items(html: str) -> list[dict]:
    """브랜드 · 카테고리 페이지 → [{id, brand, name, price, volume}].

    평점 있는 상품은 schema.org ItemList 에, 리뷰가 0개인 신상품은 상품 JSON(idProduct)에만 있다. 둘 다 읽는다.
    """
    u = unescape(unescape(html))
    out: dict[int, dict] = {}
    for r, b, n, i in re.findall(r'"name":"(\d+)위 ([^"]+?) \| ([^"]+)","image":"[^"]*","url":"https://www\.glowpick\.com/products/(\d+)"', u):
        out[int(i)] = {"id": int(i), "brand": b, "name": n}
    for i, title, vol, price in re.findall(r'"idProduct":(\d+),"idBrand":\d+,"productTitle":"([^"]*)","volume":"([^"]*)","price":(\d+)', u):
        it = out.setdefault(int(i), {"id": int(i), "brand": "", "name": title})
        it.update(volume=vol, price=int(price))
    return list(out.values())


def product_info(html: str) -> dict:
    """상품 페이지 → 평점 · 리뷰 수 · 이름 · 용량 · 가격 · 이미지 · 브랜드 번호."""
    u = unescape(unescape(html))
    out: dict = {}
    m = re.search(r'"ratingValue":"([\d.]+)","bestRating":5,"worstRating":1,"reviewCount":(\d+)', u)
    if m:
        out["rating"], out["reviews"] = float(m.group(1)), int(m.group(2))
    m = re.search(r'"idProduct":(\d+),"idBrand":(\d+),"productTitle":"([^"]*)","volume":"([^"]*)","price":(\d+)', u)
    if m:
        out.update(id=int(m.group(1)), brand_id=int(m.group(2)), title=m.group(3), volume=m.group(4), price=int(m.group(5)))
    m = re.search(r'og:image" content="([^"]+)', html or "")
    out["image"] = m.group(1) if m else None
    b = re.search(r"/brands/(\d+)", html or "")
    if b and "brand_id" not in out:
        out["brand_id"] = int(b.group(1))
    return out


def brand_title(html: str) -> tuple[str, str]:
    """브랜드 페이지 제목 "베라모어 VERAMORE 추천 제품 TOP20" → (한글명, 영문명)."""
    m = re.search(r"<title>([^<]+?) 추천 제품", html or "")
    if not m:
        return "", ""
    parts = m.group(1).split()
    kor = " ".join(p for p in parts if re.search(r"[가-힣]", p))
    eng = " ".join(p for p in parts if not re.search(r"[가-힣]", p))
    return kor, eng


_BRAND_OBJ = re.compile(r'"idBrand":(\d+),"createdAt":"[^"]*","updatedAt":"[^"]*","brandTitle":"[^"]*","name":"([^"]*)","subName":"([^"]*)"')


def brand_index(html_pages) -> dict[str, int]:
    """글로우픽 페이지들 속 브랜드 객체 → {정규형 브랜드명(한글 · 영문): 브랜드 번호}.

    상품 · 카테고리 · 브랜드 페이지마다 {"idBrand", "name"(한글), "subName"(영문)} 이 들어 있다. 받아 둔 페이지가
    늘수록 색인도 커진다. 손으로 만드는 브랜드 표가 아니다.
    """
    out: dict[str, int] = {}
    for html in html_pages:
        for bid, kor, eng in _BRAND_OBJ.findall(unescape(unescape(html))):
            if int(bid) <= 0:
                continue
            for n in (kor, eng):
                if canon(n):
                    out.setdefault(canon(n), int(bid))
    return out


class Glowpick:
    """허용 경로만 읽는 캐시 클라이언트. fetch 는 주입받는다(테스트에서 가짜로 바꾼다)."""

    def __init__(self, cache_dir: Path, fetch: Optional[Callable[[str], str]] = None, delay: float = 1.5):
        self.cache = Path(cache_dir); self.cache.mkdir(parents=True, exist_ok=True)
        self._fetch = fetch
        self.delay = delay
        self.requests = 0

    def get(self, path: str) -> str:
        if path.startswith("/searches"):
            raise ValueError("robots.txt 가 막는 경로")
        key = self.cache / (path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-") + ".html")
        if key.exists():
            return key.read_text(encoding="utf-8")
        if self._fetch is None:
            import httpx

            def _f(p: str) -> str:
                r = httpx.get(BASE + p, headers={"User-Agent": "Mozilla/5.0 (compatible; hwadam-capstone-research/1.0)"},
                              timeout=30, follow_redirects=True)
                return r.text if r.status_code == 200 else ""
            self._fetch = _f
        time.sleep(self.delay)
        self.requests += 1
        text = self._fetch(path)
        if text:
            key.write_text(text, encoding="utf-8")
        return text


class MasterEnricher:
    """매칭 실패 언급 → 등록 후보. llm 은 판정 LLM(chat_json), 없으면 100점 후보만 낸다."""

    def __init__(self, gp: Glowpick, brand_ids: dict[str, int], catalog: list[dict],
                 brand_aliases: dict[str, set[str]] | None = None, llm=None):
        self.gp = gp
        self.brand_ids = {canon(k): v for k, v in brand_ids.items()}
        self.catalog = catalog
        self.brand_aliases = brand_aliases or {}
        self.llm = llm
        self._items: dict[int, list[dict]] = {}
        self._titles: dict[int, tuple[str, str]] = {}

    def brand_names(self, mention: dict, db_brand: str | None) -> list[str]:
        names = [mention.get("brand") or ""]
        if db_brand:
            names += [db_brand] + sorted(self.brand_aliases.get(db_brand, set()))
        return [n for n in dict.fromkeys(names) if n]

    def find_brand(self, names: list[str]) -> int | None:
        for n in names:
            if canon(n) in self.brand_ids:
                return self.brand_ids[canon(n)]
        for n in names:
            hits = [it for it in self.catalog if canon(it.get("brand")) == canon(n)]
            if hits:
                info = product_info(self.gp.get(f"/products/{hits[0]['id']}"))
                if info.get("brand_id"):
                    self.brand_ids[canon(n)] = info["brand_id"]
                    return info["brand_id"]
        return None

    def items(self, bid: int) -> list[dict]:
        if bid not in self._items:
            got: dict[int, dict] = {}
            for c in CATE1:
                for suffix in ([""] if c is None else [f"?cate1Id={c}&monthTerm=24"]) + ([f"?monthTerm=24"] if c is None else []):
                    html = self.gp.get(f"/brands/{bid}{suffix}")
                    if c is None and not suffix:
                        self._titles[bid] = brand_title(html)
                    for it in brand_items(html):
                        got.setdefault(it["id"], it).update({k: v for k, v in it.items() if v})
            self._items[bid] = list(got.values())
        return self._items[bid]

    async def resolve(self, mention: dict, db_brand: str | None, caption: str = "") -> dict:
        """언급 하나 → {status: found|no_brand|no_product|out_of_scope, candidate?}."""
        if mention.get("category") not in SCOPE or mention.get("mention_type") != "product":
            return {"status": "out_of_scope"}
        bid = self.find_brand(self.brand_names(mention, db_brand))
        if bid is None:
            return {"status": "no_brand"}
        kor, eng = self._titles.get(bid, ("", ""))
        prods = self.items(bid)
        if not kor:
            kor, eng = self._titles.get(bid, ("", ""))
        brand_words = {canon(kor)} | {canon(w) for w in self.brand_names(mention, db_brand)}
        from rules.product_match import normalize
        pre = {"_": {normalize(x) for x in {kor} | set(self.brand_names(mention, db_brand)) if x}}
        scored = []
        for it in prods:
            p = {"product_id": str(it["id"]), "brand": "_", "name": f"{kor} {it['name']}".strip(), "category": mention["category"]}
            s, _, _ = score_name_v12(mention["product_name"], p, pre)
            scored.append((s, it, p))
        scored.sort(key=lambda x: -x[0])
        if not scored or scored[0][0] < V12_PARTIAL_SCORE:
            return {"status": "no_product", "brand_id": bid, "best": scored[0][1]["name"] if scored else None,
                    "best_score": round(scored[0][0]) if scored else 0}
        top = [x for x in scored if x[0] >= V12_PARTIAL_SCORE][:5]
        method = "rule"
        if top[0][0] < 100 or (len(top) > 1 and top[1][0] >= 100):
            if self.llm is None:
                return {"status": "no_product", "brand_id": bid, "best": top[0][1]["name"], "best_score": round(top[0][0])}
            from prompts.product_extract import VERIFY_SYSTEM, build_verify_user
            cands = [V1Candidate(p["product_id"], "_", p["name"], mention["category"], s) for s, _, p in top]
            res = await self.llm.chat_json(system=VERIFY_SYSTEM, user=build_verify_user(caption, mention, [asdict(c) for c in cands]),
                                           timeout=60)
            choice = res.get("choice") if isinstance(res, dict) else None
            status, pid, _ = accept_choice_v1_2(choice, cands, mention, {"_": {kor}})
            if status != MATCHED:
                return {"status": "no_product", "brand_id": bid, "best": top[0][1]["name"], "best_score": round(top[0][0]),
                        "llm_choice": choice}
            it = next(x[1] for x in top if x[2]["product_id"] == pid)
            method = "llm"
        else:
            it = top[0][1]
        return {"status": "found", "method": method, "brand_id": bid,
                "candidate": {"glow_id": it["id"], "glow_brand": kor, "glow_brand_en": eng, "name": f"{kor} {it['name']}".strip(),
                              "db_brand": db_brand or (eng.upper() or kor), "category": mention["category"],
                              "price": it.get("price"), "volume": it.get("volume"),
                              "source": f"{BASE}/products/{it['id']}"}}
