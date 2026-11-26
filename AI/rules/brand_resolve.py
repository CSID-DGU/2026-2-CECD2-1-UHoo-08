"""브랜드 보정과 쇼핑 검색어 만들기 (규칙, LLM 없음, 같은 입력이면 같은 결과).

ProductMatcher v2 에서 LLM 추출(prompts/product_extract_v2) 다음 단계다.

  1) LLM 이 낸 브랜드 표기를 사전(data/brand_dictionary.json)의 대표 브랜드로 잇는다.
     영문 · 한글 · 공식 계정명(toocoolforschool_official) 아무 표기든 된다.
  2) 브랜드가 비었거나 사전에 없으면, 캡션 안에 있는 사전 브랜드로 채운다.
     캡션에 사전 브랜드가 하나뿐이면 그 브랜드. 여럿이면 제품명이 적힌 자리에서 가장 가까운 브랜드.
  3) 쇼핑 검색어 = 대표 한글명 + 제품명. 브랜드를 못 맞췄으면 제품명만.
제품명이 없는 항목은 매칭에서 뺀다(query = None).

브랜드 출처(brand_from)를 남긴다: llm(LLM 표기가 사전에 있음) · caption(캡션에서 채움) · llm_raw(LLM 표기가 사전에 없어 그대로 둠) · none.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

RESOLVE_VERSION = "brand-resolve-v1"
DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_dictionary.json"

_HANDLE_SUFFIX = re.compile(r"[._]?(official|kr|korea|global|jp|makeup|beauty|cosmetics?|skin|official_jp|store|shop)$")
_COLLAB = re.compile(r"\s+(?:x|X|×|&)\s+")
# 판매처 · 플랫폼. 사전(글로우픽)에 브랜드로 들어 있어도 제품의 브랜드로 쓰지 않는다 ("올리브영 립 시럽" 이 되지 않게)
RETAILERS = {"올리브영", "올영", "oliveyoung", "무신사", "무신사뷰티", "musinsa", "쿠팡", "coupang", "컬리", "마켓컬리", "kurly",
             "지그재그", "zigzag", "시코르", "chicor", "롭스", "lohbs", "세포라", "sephora", "29cm", "w컨셉", "에이블리", "ably",
             "네이버", "카카오", "선물하기", "신세계", "현대백화점", "롯데", "이마트", "홈플러스", "아모레몰", "올리브영온라인"}


def key(s: str | None) -> str:
    """비교용 표기: 소문자, 한글 · 영문 · 숫자만."""
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


@dataclass
class Brand:
    ko: str | None
    en: str | None
    db_brand: str | None = None
    glowpick_id: int | None = None
    aliases: list[str] = field(default_factory=list)

    @property
    def search_name(self) -> str:
        """쇼핑 검색에 쓰는 이름. 한글명이 있으면 한글명."""
        return self.ko or self.en or ""


class BrandDictionary:
    def __init__(self, entries: list[dict]):
        retail = {key(r) for r in RETAILERS}
        entries = [e for e in entries if not ({key(e.get("ko")), key(e.get("en"))} & retail)]
        self.brands = [Brand(e.get("ko"), e.get("en"), e.get("db_brand"), e.get("glowpick_id"), list(e.get("aliases") or []))
                       for e in entries]
        self.by_key: dict[str, Brand] = {}
        for b in self.brands:
            for s in [b.ko, b.en, b.db_brand, *b.aliases]:
                k = key(s)
                if k and (len(k) >= 2 or re.fullmatch(r"[가-힣]", k)):
                    self.by_key.setdefault(k, b)
        # 캡션 검색용 표기: 너무 짧거나 흔한 말은 캡션 속 검색에서 뺀다 (exact 비교에는 쓴다)
        self._scan = sorted((k for k in self.by_key if _scannable(k)), key=len, reverse=True)

    @classmethod
    def load(cls, path: Path | str = DICT_PATH) -> "BrandDictionary":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["entries"])

    def exact(self, text: str | None) -> Brand | None:
        """표기 하나 → 브랜드. 공식 계정명 꼬리(_official 등)도 떼어 본다."""
        if not text:
            return None
        k = key(text)
        if k in self.by_key:
            return self.by_key[k]
        raw = (text or "").lower().strip().lstrip("@")
        for _ in range(3):      # luna_makeup_official → luna_makeup → luna
            stem = _HANDLE_SUFFIX.sub("", raw)
            if stem == raw:
                break
            raw = stem
            if key(raw) in self.by_key:
                return self.by_key[key(raw)]
        parts = [x for x in _COLLAB.split(text) if x.strip()]
        if len(parts) > 1:      # "라네즈 X 마뗑킴" → 앞에서부터 사전에 있는 브랜드
            for part in parts:
                b = self.exact(part)
                if b:
                    return b
        return None

    def find(self, caption: str) -> list[tuple[int, Brand]]:
        """캡션 안의 사전 브랜드 [(위치, 브랜드)]. 긴 표기부터, 겹치면 먼저 잡힌 것. 공식 계정명도 잡는다."""
        low = (caption or "").lower()
        flat, pos = _flatten(low)
        taken = [False] * (len(flat) + 1)
        hits: list[tuple[int, Brand]] = []
        for k in self._scan:
            start = 0
            while (i := flat.find(k, start)) >= 0:
                j = i + len(k)
                start = i + 1
                if any(taken[i:j]) or not _word_ok(flat, i, j, k, low, pos):
                    continue
                for t in range(i, j):
                    taken[t] = True
                hits.append((pos[i], self.by_key[k]))
        hits.sort(key=lambda x: x[0])
        out, seen = [], set()
        for p, b in hits:
            if id(b) not in seen:
                seen.add(id(b))
                out.append((p, b))
        return out


def _scannable(k: str) -> bool:
    if re.fullmatch(r"[0-9]+", k):
        return False
    if re.fullmatch(r"[a-z0-9]+", k):
        return len(k) >= 3
    return len(k) >= 1      # 한 글자 한글 브랜드(맥 · 퓌)는 _word_ok 가 앞뒤를 엄격히 본다


def _flatten(low: str) -> tuple[str, list[int]]:
    """공백 · 기호를 뺀 문자열과 원래 위치. "too cool for school" 과 "toocoolforschool" 을 같이 찾으려고."""
    flat, pos = [], []
    for i, ch in enumerate(low):
        if re.match(r"[0-9a-z가-힣]", ch):
            flat.append(ch)
            pos.append(i)
    return "".join(flat), pos


def _word_ok(flat: str, i: int, j: int, k: str, low: str, pos: list[int]) -> bool:
    """찾은 표기가 다른 단어의 일부가 아닌지. 원문 기준으로 앞뒤 글자를 본다."""
    a, b = pos[i], pos[j - 1] + 1
    before = low[a - 1] if a > 0 else " "
    after = low[b] if b < len(low) else " "
    if re.fullmatch(r"[a-z0-9]+", k):
        return not re.match(r"[a-z0-9]", before) and not re.match(r"[a-z]", after)
    if re.search(r"\s", low[a:b]):
        return False        # 한글 표기는 띄어쓰기를 가로질러 잡지 않는다 ("…라 카…" ≠ 라카)
    if re.match(r"[가-힣]", before):
        return False
    if len(k) == 1:
        return not re.match(r"[가-힣]", after)      # "누가" 의 누 · "맥주" 의 맥은 브랜드가 아니다
    if len(k) <= 2 and re.match(r"[가-힣]", after):
        return after in "의에는은이가를을도랑과와"
    return True


@dataclass
class Resolved:
    brand: Brand | None
    brand_text: str | None      # LLM 이 낸 브랜드 표기 원문
    brand_from: str             # llm · caption · llm_raw · none
    product_name: str | None
    query: str | None           # 쇼핑 검색어. 제품명이 없으면 None (매칭에서 뺀다)
    query_kind: str             # brand+name · name_only · skip


def resolve(item: dict, caption: str, d: BrandDictionary) -> Resolved:
    """LLM 추출 항목 하나 {brand, product_name} → 브랜드 보정 · 검색어."""
    bt = (item.get("brand") or "").strip() or None
    name = re.sub(r"\s+", " ", (item.get("product_name") or "")).strip() or None
    brand, how = None, "none"
    if bt:
        brand = d.exact(bt)
        how = "llm" if brand else "llm_raw"
    if brand is None and not bt:
        # 캡션의 사전 브랜드로 채우는 건 LLM 이 브랜드를 비웠을 때만. LLM 이 사전에 없는 브랜드(에이쁘 · 리브러쉬)를 냈으면
        # 다른 브랜드로 덮지 않는다 — 덮으면 같은 글의 다른 브랜드가 붙는다
        found = d.find(caption)
        if len(found) == 1:
            brand, how = found[0][1], "caption"
        elif found and name:
            at = _locate(caption, name)
            if at is not None:
                brand, how = min(found, key=lambda x: abs(x[0] - at))[1], "caption"
    if name and _is_brand_only(name, brand, bt, d):
        name = None         # "Prada Beauty / Prada Beauty" — 제품명 자리에 브랜드만 있음
    if not name:
        return Resolved(brand, bt, how, None, None, "skip")
    name = _strip_brand(name, brand, bt)
    if brand is not None:
        return Resolved(brand, bt, how, name, f"{brand.search_name} {name}".strip(), "brand+name")
    return Resolved(None, bt, how, name, name, "name_only")


def _locate(caption: str, name: str) -> int | None:
    """제품명이 캡션 어디에 있나 (공백 무시). 없으면 첫 단어 위치."""
    low = caption.lower()
    flat, pos = _flatten(low)
    k = key(name)
    i = flat.find(k) if k else -1
    if i >= 0:
        return pos[i]
    first = key(name.split()[0]) if name.split() else ""
    i = flat.find(first) if first else -1
    return pos[i] if i >= 0 else None


def _strip_brand(name: str, brand: Brand | None, brand_text: str | None) -> str:
    """제품명 앞에 브랜드 표기가 붙어 있으면 뗀다 ("투쿨포스쿨 무드 스위치 팔레트" → "무드 스위치 팔레트")."""
    surfaces = {key(s) for s in ([brand_text] + ([brand.ko, brand.en, brand.db_brand, *brand.aliases] if brand else [])) if s}
    ws = name.split()
    while len(ws) > 1 and key(ws[0]) in surfaces:
        ws = ws[1:]
    return " ".join(ws)


def _is_brand_only(name: str, brand: Brand | None, brand_text: str | None, d: BrandDictionary) -> bool:
    k = key(name)
    if brand_text and k == key(brand_text):
        return True
    if brand and k in {key(x) for x in [brand.ko, brand.en, brand.db_brand, *brand.aliases] if x}:
        return True
    return d.exact(name) is not None and len(name.split()) <= 2
