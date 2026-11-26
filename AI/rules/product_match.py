"""인스타 캡션에서 언급된 제품을 상품 마스터와 문자열 유사도로 잇는다 (ProductMatcher v0).

LLM · 브랜드 별칭 사전 없이 RapidFuzz 만 쓴다. 규칙만으로 어디까지 되는지
재 보는 실험 버전이라, 결과는 DB 에 쓰지 않고 평가 스크립트가 CSV 로 낸다
(scripts/evaluate_product_match.py).

잘못 잇는 것보다 잇지 않는 편이 낫다. 트렌드 지수는 매칭 결과를 그대로
세므로, 엉뚱한 제품에 붙은 언급 하나가 그 제품의 순위를 올린다. 그래서
점수가 높아도 일반 단어(틴트 · 쿠션 · 크림 …)만 겹치면 잇지 않고, 다른 제품과
같은 자리를 두고 다투면 사람이 보도록 review 로 넘긴다.

비교는 캡션 한 줄과 제품명 사이에서 한다. 캡션 전체와 비교하면 긴 글에 흩어진
단어들이 우연히 맞아 점수가 오른다. 제품 정보는 대개 한 줄에 몰려 있다.

제품 단위로 잇는다. 호수 · 컬러 · 용량 · 기획 구성은 제품명에서 떼고 비교한다.
같은 제품이 단품 / 기획 / 호수별로 여러 행이면, 한 자리에 함께 걸린 것은
같은 제품군으로 보고 이름이 가장 짧은 행 하나로 잇는다.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

MATCH_VERSION = "match-v0.1"

MATCHED = "matched"
REVIEW = "review"
UNMATCHED = "unmatched"

AUTO_THRESHOLD = 95   # 이 점수 이상이고 근거가 고유하면 자동으로 잇는다. 90 에서는 같은 브랜드 다른 제품이 붙었다
REVIEW_THRESHOLD = 70  # 이 점수 이상이면 후보로 남겨 사람이 본다
BRAND_THRESHOLD = 90  # 같은 줄 근처에 그 제품의 브랜드 표기가 있으면 이 점수부터 자동으로 잇는다
CONFLICT_GAP = 8      # 같은 자리를 두고 이 점수 차 안에서 다른 제품이 걸리면 충돌
BRAND_WINDOW = 1      # 브랜드 표기를 찾는 범위: 후보가 걸린 줄의 앞뒤 몇 줄까지
MIN_DISTINCT_CHARS = 2  # 일반 단어를 뺀 뒤 남아야 하는 글자 수 ("블랙 쿠션" 의 '블랙')
MIN_NAME_CHARS = 6      # 공백을 뺀 이름 전체 길이. 짧은 이름은 우연히 겹친다
TOP_K = 5

# 제품 종류를 가리킬 뿐 어느 제품인지는 말해 주지 않는 단어
GENERIC = {
    "립", "틴트", "립틴트", "글로스", "립글로스", "립스틱", "립밤", "밤", "립오일", "오일", "립라이너", "라이너",
    "쿠션", "파운데이션", "컨실러", "프라이머", "팩트", "베이스",
    "크림", "세럼", "앰플", "에센스", "토너", "로션", "미스트", "마스크", "패드", "젤",
    "선크림", "선스틱", "선쿠션", "선세럼", "선에센스", "선스크린", "썬크림", "썬스틱", "선", "썬",
    "수분", "수분크림", "진정", "보습", "톤업", "커버", "매트", "글로우", "촉촉", "스틱", "핏",
    "lip", "tint", "gloss", "balm", "cushion", "cream", "serum", "toner", "sun", "stick",
}

# 제품명에 붙지만 캡션에서는 자주 빠지는 버전 표기. 고유 단어 검사에서 뺀다
VERSION_WORDS = {"올뉴", "뉴", "new", "ex", "리뉴얼", "뉴클래스", "신형", "ad"}
# 단어 검사에서 빼는 관사류. 한 글자라고 다 빼면 "팁" · "팟" 처럼 제품을 가르는 말까지 빠진다
STOP_WORDS = {"더", "the"}

# 캡션 본문에 @ 없이 적히는 브랜드 공식 계정명 ("torriden_official", "fwee_makeup")
_HANDLE = re.compile(r"(?<![a-z0-9_.])([a-z0-9][a-z0-9_.]{2,})_(official|kr|korea|global|jp|makeup|beauty|cosmetics?|official_jp)(?![a-z0-9_])")

# 제품명에서 떼어 낼 구성 · 옵션 표기
_BRACKET = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_VOLUME = re.compile(r"\d+(?:\.\d+)?\s*(?:ml|g|매|colors?)\b|\d+\s*\+\s*\d+", re.IGNORECASE)
# 단어 전체가 구성 표기일 때만 뗀다. 단어 안의 "더블"("더블웨어")까지 지우면 다른 제품과 겹친다
# "트리플" 은 넣지 않는다. "트리플 팟 컨실러" 처럼 제품명이고, 묶음 표기는 대개 괄호 안이라 이미 떨어진다
_PACKAGE_WORD = re.compile(r"(?:기획|더블|단품|리필|증정|세트|본품)+")
_SPF = re.compile(r"spf\s*\d+\+?|pa\s*\+{1,4}", re.IGNORECASE)
# "07 쇼콜라 티", "11 누디 보틀", "03 실루엣" 처럼 숫자로 시작하는 호수 꼬리
_SHADE_TAIL = re.compile(r"\s\d{1,3}(?:호)?\s+\S.*$|\s\d{1,3}호$")
_KEEP = re.compile(r"[^0-9a-z가-힣&+\s]")


def normalize(text: str) -> str:
    """소문자 · 전각 정리 · 기호 제거 · 공백 하나로. 줄바꿈은 split_lines 가 먼저 나눈다."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = _KEEP.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def compact(text: str) -> str:
    return text.replace(" ", "")


def split_lines(caption: str) -> list[str]:
    """캡션을 비교 단위로 나눈다. 빈 줄 · 해시태그만 있는 줄도 남긴다 (#제품명 으로 적는 경우가 있다)."""
    lines = []
    for raw in (caption or "").splitlines():
        line = normalize(raw.replace("#", " "))
        if line:
            lines.append(line)
    return lines


def core_name(name: str) -> str:
    """제품명에서 구성 · 용량 · 호수 · SPF 를 뗀 핵심 이름."""
    t = _BRACKET.sub(" ", name or "")
    t = _SPF.sub(" ", t)
    t = _VOLUME.sub(" ", t)
    t = " ".join(w for w in normalize(t).split() if not _PACKAGE_WORD.fullmatch(w))
    cut = _SHADE_TAIL.sub("", " " + t).strip()
    # 호수를 뗀 뒤 한 단어만 남으면 그 단어는 대개 브랜드다 ("peripera 06 morning sunshine cheek")
    return cut if len(cut.split()) >= 2 else t


def distinct_chars(name: str) -> int:
    """일반 단어를 뺀 뒤 남는 글자 수. 이 값이 작으면 이름만으로 제품을 가를 수 없다."""
    return sum(len(w) for w in name.split() if w not in GENERIC)


def brand_prefixes(products: list[dict]) -> dict[str, set[str]]:
    """브랜드별로, 상품명 첫 단어로 확인되는 브랜드 표기를 모은다.

    별칭 사전을 손으로 만들지 않는다. 같은 브랜드의 상품명 둘 이상이 같은 첫 단어로
    시작하면 그 단어는 브랜드 표기다 ("롬앤 더 쥬시 래스팅 틴트", "롬앤 블러 퍼지 틴트").
    브랜드 영문명이 그대로 첫 단어인 경우("MAC …")도 넣는다.
    """
    counts: dict[tuple[str, str], int] = {}
    out: dict[str, set[str]] = {}
    for p in products:
        brand = p.get("brand") or ""
        words = normalize(p.get("name") or "").split()
        if not words:
            continue
        counts[(brand, words[0])] = counts.get((brand, words[0]), 0) + 1
        if words[0] == normalize(brand):
            out.setdefault(brand, set()).add(words[0])
    for (brand, word), n in counts.items():
        if n >= 2:
            out.setdefault(brand, set()).add(word)
    return out


def search_names(product: dict, prefixes: dict[str, set[str]]) -> list[str]:
    """비교에 쓸 이름들. 핵심 이름, 그리고 확인된 브랜드 표기를 뗀 이름."""
    core = core_name(product.get("name") or "")
    names = [core] if core else []
    words = core.split()
    if len(words) > 1 and words[0] in prefixes.get(product.get("brand") or "", set()):
        names.append(" ".join(words[1:]))
    # 버전 표기("올뉴", "NEW")는 캡션에서 자주 빠지므로 뗀 이름도 비교한다
    names += [" ".join(w for w in n.split() if w not in VERSION_WORDS) for n in list(names)]
    # 일반 단어만 남는 이름, 브랜드 표기뿐인 이름은 비교하지 않는다
    brand_words = prefixes.get(product.get("brand") or "", set()) | {normalize(product.get("brand") or "")}
    return [n for n in dict.fromkeys(names)
            if n not in brand_words
            and distinct_chars(n) >= MIN_DISTINCT_CHARS and len(compact(n)) >= MIN_NAME_CHARS]


def find_handles(caption: str) -> list[str]:
    """캡션에 적힌 브랜드 공식 계정명들 (소문자)."""
    return [m.group(0) for m in _HANDLE.finditer((caption or "").lower())]


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def brand_from_handle(handle: str, brands: list[str]) -> str | None:
    """공식 계정명 → products.brand. 확실할 때만 돌려준다.

    접미사(_official 등)를 뗀 이름에 브랜드 영문명이 그대로 들어 있어야 한다
    ("herabeauty" ⊃ "hera"). 두 브랜드 이상이 들어맞으면 가장 긴 쪽, 길이도 같으면 모른다.
    """
    m = _HANDLE.fullmatch(handle.lower())
    stem = _alnum(m.group(1) if m else handle)
    hits = [b for b in brands if len(_alnum(b)) >= 3 and _alnum(b) in stem]
    if not hits:
        return None
    hits.sort(key=lambda b: -len(_alnum(b)))
    if len(hits) > 1 and len(_alnum(hits[0])) == len(_alnum(hits[1])):
        return None
    return hits[0]


def brand_marks(product: dict, prefixes: dict[str, set[str]], handle_brands: dict[str, str]) -> set[str]:
    """캡션에서 이 제품의 브랜드를 가리키는 표기들 (공백 없앤 소문자)."""
    brand = product.get("brand") or ""
    marks = {compact(normalize(brand))} | {compact(w) for w in prefixes.get(brand, set())}
    marks |= {h for h, b in handle_brands.items() if b == brand}
    return {m for m in marks if len(m) >= 2}


def missing_words(sname: str, line: str, brand_words: set[str]) -> list[str]:
    """제품명 단어 중 그 줄에 없는 것. 브랜드 표기 · 버전 표기 · 관사("더")는 따지지 않는다.

    일반 단어도 따진다. 같은 라인 안에서는 "스틱" 과 "세럼" 이 제품을 가른다.
    """
    cl = compact(line)
    return [w for w in sname.split()
            if w not in VERSION_WORDS and w not in STOP_WORDS and w not in brand_words and compact(w) not in cl]


@dataclass
class Candidate:
    product_id: str
    name: str
    score: float
    line_no: int
    matched_text: str
    search_name: str
    span: tuple[int, int] = (0, 0)
    status: str = REVIEW
    reason: str = ""
    family: list[str] = field(default_factory=list)
    brand_confirmed: bool = False
    missing: list[str] = field(default_factory=list)


def _best_in_line(sname: str, line: str) -> tuple[float, str, tuple[int, int]]:
    """한 줄 안에서 이름과 가장 비슷한 구간과 점수."""
    if compact(sname) in compact(line):
        # 공백만 다른 정확 포함. 원문 구간은 정렬로 찾는다
        al = fuzz.partial_ratio_alignment(sname, line)
        return 100.0, line[al.dest_start:al.dest_end], (al.dest_start, al.dest_end)
    if len(line) < len(sname) * 0.6:
        return 0.0, "", (0, 0)
    al = fuzz.partial_ratio_alignment(sname, line, score_cutoff=REVIEW_THRESHOLD)
    if not al:
        return 0.0, "", (0, 0)
    return al.score, line[al.dest_start:al.dest_end], (al.dest_start, al.dest_end)


def _overlap(a: Candidate, b: Candidate) -> bool:
    return a.line_no == b.line_no and a.span[0] < b.span[1] and b.span[0] < a.span[1]


def match_caption(caption: str, products: list[dict], prefixes: dict[str, set[str]] | None = None,
                  handle_brands: dict[str, str] | None = None) -> list[Candidate]:
    """캡션 하나 → 제품 후보 목록 (점수 순). 각 후보에 status 와 근거가 붙는다.

    products: [{product_id, brand, name}]
    handle_brands: 공식 계정명 → products.brand. 없으면 이 캡션의 계정명으로 바로 만든다.
    반환: matched · review 후보만. 하나도 없으면 빈 목록(= 미매칭).
    """
    prefixes = prefixes if prefixes is not None else brand_prefixes(products)
    lines = split_lines(caption)
    if not lines:
        return []
    if handle_brands is None:
        brands = sorted({p.get("brand") or "" for p in products} - {""})
        handle_brands = {h: b for h in find_handles(caption) if (b := brand_from_handle(h, brands))}
    by_id = {p["product_id"]: p for p in products}
    compact_lines = [compact(line) for line in lines]

    cands: list[Candidate] = []
    for p in products:
        best: Candidate | None = None
        for sname in search_names(p, prefixes):
            for i, line in enumerate(lines):
                score, text, span = _best_in_line(sname, line)
                if score >= REVIEW_THRESHOLD and (best is None or score > best.score):
                    best = Candidate(p["product_id"], p.get("name") or "", score, i, text, sname, span)
        if best:
            cands.append(best)
    cands.sort(key=lambda c: (-c.score, len(c.name)))
    cands = cands[:TOP_K * 4]

    # 같은 자리에 걸린 같은 제품군(핵심 이름이 같은 행들)은 하나로 묶는다
    merged: list[Candidate] = []
    for c in cands:
        same = next((m for m in merged if _overlap(m, c) and compact(core_name(m.name)) == compact(core_name(c.name))), None)
        if same:
            same.family.append(c.product_id)
            if len(c.name) < len(same.name):  # 이름이 가장 짧은 행(대개 단품)으로 잇는다
                same.family.append(same.product_id)
                same.family.remove(c.product_id)
                same.product_id, same.name = c.product_id, c.name
            continue
        merged.append(c)

    for c in merged:
        p = by_id[c.product_id]
        marks = brand_marks(p, prefixes, handle_brands)
        window = "".join(compact_lines[max(0, c.line_no - BRAND_WINDOW): c.line_no + BRAND_WINDOW + 1])
        c.brand_confirmed = any(m in window for m in marks)
        brand_words = prefixes.get(p.get("brand") or "", set()) | {normalize(p.get("brand") or "")}
        c.missing = [] if c.score == 100 else missing_words(c.search_name, lines[c.line_no], brand_words)
        threshold = BRAND_THRESHOLD if c.brand_confirmed else AUTO_THRESHOLD
        # 정확 포함(100)은 정확 포함끼리만 다툰다. 비슷하기만 한 이름에 지면 안 된다
        rivals = [o for o in merged if o is not c and _overlap(o, c)
                  and (o.score == 100 if c.score == 100 else o.score >= c.score - CONFLICT_GAP)]
        if c.score < threshold:
            c.status, c.reason = REVIEW, f"점수가 자동 기준({threshold})보다 낮음"
        elif distinct_chars(normalize(c.matched_text)) < MIN_DISTINCT_CHARS or len(compact(c.matched_text)) < MIN_NAME_CHARS:
            c.status, c.reason = REVIEW, "일치한 부분이 일반 단어뿐"
        elif c.missing:
            c.status, c.reason = REVIEW, "제품명 단어가 캡션에 없음: " + ", ".join(c.missing)
        elif rivals:
            # 한 이름이 다른 이름을 품으면(긴 쪽이 더 구체적) 긴 쪽만 자동으로 본다
            if all(len(compact(c.search_name)) > len(compact(o.search_name)) and compact(o.search_name) in compact(c.search_name) for o in rivals):
                c.status, c.reason = MATCHED, "더 구체적인 이름이 포함 관계로 이김"
            else:
                c.status, c.reason = REVIEW, "같은 자리를 두고 다른 제품과 충돌: " + ", ".join(o.name for o in rivals[:3])
        else:
            c.status, c.reason = MATCHED, ("정확 포함" if c.score == 100 else "유사도 높음") + (" · 브랜드 확인" if c.brand_confirmed else "")
    # 더 구체적인 이름에 진 짧은 이름은 따로 남기지 않는다
    winners = [c for c in merged if c.status == MATCHED]
    merged = [c for c in merged if not (c.status == REVIEW and any(_overlap(w, c) and compact(c.search_name) in compact(w.search_name) for w in winners))]
    return sorted(merged, key=lambda c: (c.status != MATCHED, -c.score))[:TOP_K]


# ══ ProductMatcher v1: LLM 이 추출한 언급 → DB 후보 → 판정 ═══════════════════════
#
# v0.1(위)은 캡션 줄과 상품명을 직접 비교했다. v1 은 LLM 이 캡션에서 뽑은 언급
# {brand, product_name, category} 하나를 상품 마스터와 비교한다. 비교 · 판정 규칙은
# 여기 두고 LLM 호출은 services/product_matcher_v1 이 한다. v0.1 함수는 기준선이라
# 고치지 않는다.

MATCH_V1_VERSION = "match-v1"
V1_AUTO_SCORE = 95     # 규칙으로 자동 확정하는 이름 점수
V1_GAP = 8             # 1 · 2 위 후보의 이름 점수 차
V1_TOP_K = 5
SCOPE = {"base", "sun", "lip", "skincare"}
V1_VERIFY_MIN = 60     # 판정 LLM 에 넘길 후보의 최소 이름 점수. 그 아래는 LLM 이 그럴듯한 이유를 붙여 고른다
V1_UNKNOWN_BRAND_MIN = 90  # 브랜드 표기가 DB 와 이어지지 않을 때 전체 상품에서 찾는 후보의 최소 이름 점수
# 판정 LLM 이 고른 후보의 이름에서 빠져도 되는 단어: 제품 종류뿐이다("쥬시래스팅" ↔ "더 쥬시 래스팅 틴트").
# 마무리 · 라인을 가르는 말("매트", "글로우", "스틱")이 빠지면 다른 제품일 수 있어 인정하지 않는다
TYPE_WORDS = {
    "틴트", "립틴트", "글로스", "립글로스", "립스틱", "립밤", "밤", "립오일", "쿠션", "파운데이션", "컨실러", "프라이머",
    "크림", "세럼", "앰플", "에센스", "토너", "로션", "오일", "선크림", "선스틱", "선쿠션", "선세럼", "선에센스",
    "선스크린", "썬크림", "썬스틱", "립", "선", "썬",
}


def brand_keys(products: list[dict], prefixes: dict[str, set[str]], handle_brands: dict[str, str] | None = None) -> dict[str, str]:
    """캡션 표기(공백 없앤 소문자) → products.brand. 영문명 · 한글 브랜드 표기 · 공식 계정명."""
    keys: dict[str, str] = {}
    for b in {p.get("brand") or "" for p in products} - {""}:
        keys[compact(normalize(b))] = b
        keys[_alnum(b)] = b
        for w in prefixes.get(b, set()):
            keys[compact(w)] = b
    for h, b in (handle_brands or {}).items():
        keys[compact(h)] = b
    return {k: v for k, v in keys.items() if len(k) >= 2}


_HANGUL = re.compile(r"^[가-힣]{2,}$")


def weak_brand_keys(products: list[dict]) -> dict[str, str]:
    """상품명 첫 단어로 짐작하는 한글 브랜드 표기 ("클리오 킬 커버 파운웨어 쿠션 올뉴" → 클리오).

    같은 브랜드 상품 둘 이상이 그 단어로 시작해야 하는 brand_prefixes 를 못 넘는 브랜드가 많다
    (CLIO · LANEIGE 는 한글 이름으로 시작하는 상품이 하나뿐이다). 세 단어 이상인 이름의 첫 단어이고
    다른 브랜드에서는 첫 단어로 안 쓰일 때만 넣는다. 두 단어 이름("더블웨어 파운데이션")의 첫 단어는
    제품 라인일 수 있어 넣지 않는다. resolve_brand 는 이 표기를 정확히 같을 때만 쓴다.
    """
    seen: dict[str, set[str]] = {}
    for p in products:
        words = normalize(p.get("name") or "").split()
        if len(words) >= 3 and _HANGUL.match(words[0]) and words[0] not in GENERIC:
            seen.setdefault(words[0], set()).add(p.get("brand") or "")
    return {w: next(iter(bs)) for w, bs in seen.items() if len(bs) == 1 and "" not in bs}


def resolve_brand(text: str | None, keys: dict[str, str], weak: dict[str, str] | None = None) -> str | None:
    """추출한 브랜드 표기 → products.brand. 확실히 하나로 정해질 때만.

    keys(영문명 · 확인된 한글 표기 · 공식 계정명)는 부분 일치도 보고, weak(상품명 첫 단어로 짐작한
    한글 표기)는 정확히 같을 때만 쓴다.
    """
    if not text:
        return None
    t = compact(normalize(text))
    if t in keys:
        return keys[t]
    if weak and t in weak:
        return weak[t]
    a = _alnum(text)
    if a and a in keys:
        return keys[a]
    hits = {b for k, b in keys.items() if len(k) >= 3 and (k in t or (len(t) >= 3 and t in k))}
    return hits.pop() if len(hits) == 1 else None


def score_name(query: str, product: dict, prefixes: dict[str, set[str]]) -> tuple[float, str, list[str]]:
    """추출한 제품명 ↔ 상품 하나. (점수, 비교에 쓴 이름, 상품명에만 있는 단어)."""
    q = core_name(query)
    best = (0.0, "", [])
    brand = product.get("brand") or ""
    brand_words = prefixes.get(brand, set()) | {normalize(brand)}
    for sname in search_names(product, prefixes):
        cq, cs = compact(q), compact(sname)
        if cq and (cq == cs or (cs in cq) or (cq in cs and len(cq) >= 0.8 * len(cs))):
            score = 100.0
        else:
            score = max(fuzz.ratio(cq, cs), fuzz.token_sort_ratio(q, sname))
        miss = missing_words(sname, q, brand_words)
        if score > best[0]:
            best = (score, sname, miss)
    return best


@dataclass
class V1Candidate:
    product_id: str
    brand: str
    name: str
    category: str | None
    name_score: float
    embed_score: float = 0.0
    search_name: str = ""
    missing: list[str] = field(default_factory=list)
    alias: bool = False   # v1.2: 확인된 별칭 사전(data/product_aliases.json)으로 찾은 후보


def rank_candidates(mention: dict, products: list[dict], prefixes: dict[str, set[str]], keys: dict[str, str],
                    embed_scores: dict[str, float] | None = None, top_k: int = V1_TOP_K,
                    weak: dict[str, str] | None = None) -> tuple[str | None, list[V1Candidate]]:
    """언급 하나 → (확인된 브랜드, 후보 TOP k).

    - 브랜드가 확인되면 그 브랜드 상품만 본다.
    - 브랜드 표기가 있는데 DB 에 없는 브랜드면 후보가 없다(미등록 제품).
    - 카테고리가 4개 안이면 다른 카테고리 상품을 뺀다. 범위 밖(other)이면 후보가 없다.
    - 이름 점수(RapidFuzz) 순으로 고르고, 임베딩 점수가 높은 상품을 후보에 더한다.
    """
    if mention.get("mention_type") != "product" or not mention.get("product_name"):
        return None, []
    cat = mention.get("category")
    if cat == "other":
        return None, []
    if weak is None:
        weak = weak_brand_keys(products)
    brand = resolve_brand(mention.get("brand"), keys, weak)
    unknown_brand = False
    if mention.get("brand") and brand is None:
        # 상품명 안에 브랜드가 들어 있는 경우("롬앤 쥬시래스팅")를 한 번 더 본다
        brand = resolve_brand(mention.get("product_name"), keys)
        # 그래도 모르면: DB 에 없는 브랜드이거나, 한글 표기가 사전에 없는 브랜드다("클리오").
        # 전체 상품에서 이름이 거의 같은 것만 후보로 남긴다. 브랜드가 확인되지 않았으니 규칙 확정은 없다
        unknown_brand = brand is None
    # 비교용 이름에서 떼는 브랜드 표기에 짐작한 한글 표기도 넣는다 (v0.1 의 search_names 는 그대로다)
    pre = {b: set(ws) for b, ws in prefixes.items()}
    for w, b in weak.items():
        pre.setdefault(b, set()).add(w)
    pool = [p for p in products
            if (brand is None or p.get("brand") == brand) and (cat not in SCOPE or p.get("category") == cat)]
    embed_scores = embed_scores or {}
    scored = []
    for p in pool:
        s, sname, miss = score_name(mention["product_name"], p, pre)
        scored.append(V1Candidate(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                  s, embed_scores.get(p["product_id"], 0.0), sname, miss))
    if unknown_brand:
        scored = [c for c in scored if c.name_score >= V1_UNKNOWN_BRAND_MIN]
    by_name = sorted(scored, key=lambda c: (-c.name_score, -c.embed_score))[:top_k]
    by_embed = [] if unknown_brand else sorted((c for c in scored if c.embed_score > 0), key=lambda c: -c.embed_score)[:2]
    merged = list({c.product_id: c for c in by_name + by_embed}.values())
    merged.sort(key=lambda c: (-c.name_score, -c.embed_score))
    return brand, merged[:top_k]


def auto_decide(mention: dict, brand: str | None, cands: list[V1Candidate]) -> tuple[str, str | None, str]:
    """(status, product_id, 사유). status: matched · verify · unmatched · brand_only · category_only.

    규칙으로 확정하는 건 이름이 거의 같고(95+), 브랜드가 확인됐고, 2위와 8점 이상 차이 나고,
    상품명 단어가 빠지지 않은 경우뿐이다. 나머지 후보가 있는 경우는 판정 LLM 에 넘긴다(verify).
    """
    mt = mention.get("mention_type")
    if mt in ("brand_only", "category_only"):
        return mt, None, "제품을 특정할 수 없는 언급"
    if not cands:
        return "unmatched", None, "DB 후보 없음"
    top = cands[0]
    second = cands[1].name_score if len(cands) > 1 else 0.0
    if brand and top.brand == brand and top.name_score >= V1_AUTO_SCORE and top.name_score - second >= V1_GAP and not top.missing:
        return MATCHED, top.product_id, "규칙 확정: 브랜드 일치 · 이름 일치"
    if top.name_score < V1_VERIFY_MIN:
        return "unmatched", None, f"이름이 비슷한 후보 없음 (최고 {top.name_score:.0f}점)"
    return "verify", None, "규칙으로 정하지 못함"


def verify_pool(cands: list[V1Candidate]) -> list[V1Candidate]:
    """판정 LLM 에 보여 줄 후보. 이름 점수가 너무 낮은 후보는 빼서 억지 선택을 막는다."""
    return [c for c in cands if c.name_score >= V1_VERIFY_MIN]


def accept_choice(choice: object, cands: list[V1Candidate]) -> tuple[str, str | None]:
    """판정 LLM 의 답을 검사한다. 후보 밖의 ID 나 형식이 틀린 답은 review 로 둔다."""
    if not isinstance(choice, str):
        return REVIEW, None
    if choice in ("review", "unmatched"):
        return choice, None
    picked = next((c for c in cands if c.product_id == choice), None)
    if picked is None:
        return REVIEW, None
    # LLM 이 골랐어도, 추출명에 없는 단어가 제품 종류 말이 아니면(마무리 · 라인 차이) 사람이 본다
    if any(w not in TYPE_WORDS for w in picked.missing):
        return REVIEW, None
    return MATCHED, choice


# ══ ProductMatcher v1.1 실험: 판정 LLM 이 고른 후보의 빠진 단어 검사 완화 ════════════════
#
# v1 의 accept_choice 는 LLM 이 고른 후보 이름에 추출명에 없는 단어가 하나라도 있으면(제품 종류
# 말 제외) review 로 돌린다. 235개 실험에서 이 검사로 막힌 7건 중 다수는 같은 제품이었다:
# 이름 앞의 한글 브랜드 표기("퓌", "조선미녀"), "논-스틱" 이 "논 / 스틱" 으로 쪼개진 것,
# 추출 단계가 브랜드 칸으로 옮긴 원문 단어("누 글로우 화이트 쿠션" 의 "누") 따위다.
# v1.1 은 빠진 단어가 "제품을 가르는 말" 일 때만 막는다. v1 함수는 비교 기준이라 고치지 않는다.
#
# 인정 조건 (모두 만족해야 matched)
#   1. 추출명의 단어가 모두 후보 이름에 있다. LLM 이 다른 이름을 고른 것("뮤이" → "매트")은 막는다
#   2. 후보 이름에만 있는 단어 하나하나가 다음 중 하나다
#      - 제품 종류 말(TYPE_WORDS) · 버전 표기 · 관사
#      - 원문 근거(evidence) · 추출한 브랜드 칸에 그대로 있는 말
#      - 그 브랜드의 확인된 한글 표기(data/brand_aliases.json)
#      - 마무리 · 제형 말(FINISH_WORDS)이 아니고, 같은 브랜드 · 같은 종류의 다른 후보도 가진 말
#        (또는 다른 후보가 없음). 다른 후보와 가르는 말이 빠졌으면 막는다
#   3. 호수만 다른 쌍둥이 후보가 있으면 고른 후보의 호수 표기가 원문 근거에 있어야 한다

MATCH_V1_1_VERSION = "match-v1.1"
# 같은 라인 안에서 제품을 가르는 마무리 · 제형 말. 빠지면 다른 제품일 수 있다
FINISH_WORDS = {
    "매트", "글로우", "새틴", "벨벳", "듀이", "스틱", "펜슬", "팁", "팟", "트리플", "리퀴드", "파우더", "젤",
    "블러", "샤인", "톤업", "커버", "matte", "glow", "velvet", "stick", "pencil",
}
_HYPHEN = re.compile(r"(?<=[0-9a-z가-힣])-(?=[0-9a-z가-힣])", re.IGNORECASE)
_ALNUM_CHAR = re.compile(r"[0-9a-z가-힣]")  # "+" 처럼 기호만 남은 조각은 단어로 치지 않는다


def _v11_words(name: str) -> list[str]:
    """비교용 단어. "논-스틱" 처럼 하이픈으로 붙은 말은 한 단어로 둔다."""
    return core_name(_HYPHEN.sub("", name or "")).split()


def accept_choice_v1_1(choice: object, cands: list[V1Candidate], mention: dict,
                       brand_aliases: dict[str, set[str]] | None = None) -> tuple[str, str | None, str]:
    """판정 LLM 의 답을 v1.1 규칙으로 검사한다. (status, product_id, 사유)."""
    if not isinstance(choice, str):
        return REVIEW, None, "판정 응답 형식이 틀림"
    if choice in ("review", "unmatched"):
        return choice, None, "판정 LLM 이 고르지 않음"
    picked = next((c for c in cands if c.product_id == choice), None)
    if picked is None:
        return REVIEW, None, "후보 밖의 답"

    ext_words = _v11_words(mention.get("product_name") or "")
    ext_c = compact(" ".join(ext_words))
    pick_words = _v11_words(picked.name)
    pick_c = compact(" ".join(pick_words))
    lacking = [w for w in ext_words if compact(w) not in pick_c and w not in TYPE_WORDS]
    if lacking and ext_c not in pick_c:
        return REVIEW, None, "추출명 단어가 후보 이름에 없음: " + ", ".join(lacking)

    said = compact(normalize(f"{mention.get('evidence') or ''} {mention.get('brand') or ''}"))
    aliases = {compact(a) for a in (brand_aliases or {}).get(picked.brand, set())}
    siblings = [c for c in cands if c.product_id != picked.product_id and c.brand == picked.brand and c.category == picked.category]
    sib_words = [{compact(w) for w in _v11_words(c.name)} for c in siblings]
    for w in pick_words:
        cw = compact(w)
        if cw in ext_c or w in TYPE_WORDS or w in VERSION_WORDS or w in STOP_WORDS or not _ALNUM_CHAR.search(w):
            continue
        if cw in said or cw in aliases:
            continue
        if w in FINISH_WORDS:
            return REVIEW, None, f"마무리 · 제형 말이 빠짐: {w}"
        if any(cw not in ws for ws in sib_words):
            return REVIEW, None, f"같은 브랜드 다른 후보와 가르는 말이 빠짐: {w}"

    twins = [c for c in siblings if _v11_words(c.name) == pick_words]
    if twins:
        shade = [w for w in normalize(_HYPHEN.sub("", picked.name)).split() if compact(w) not in pick_c and not w.isdigit()]
        if not shade or not all(compact(w) in said for w in shade):
            return REVIEW, None, "호수만 다른 후보가 있는데 고른 호수가 원문에 없음"
    return MATCHED, choice, "v1.1 인정"


def load_brand_aliases(path=None) -> dict[str, set[str]]:
    """확인된 브랜드 한글 표기 (data/brand_aliases.json). products.brand → {표기}."""
    import json
    from pathlib import Path

    p = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "brand_aliases.json"
    if not p.exists():
        return {}
    out: dict[str, set[str]] = {}
    for row in json.loads(p.read_text(encoding="utf-8")):
        out.setdefault(row["brand"], set()).add(row["alias"])
    return out


# ══ ProductMatcher v1.2: 후보 검색 보강 + 판정 규칙 정리 ══════════════════════════════
#
# v1.1 까지 못 잡은 언급은 대부분 표기 차이였다 (235개 게시물 검토, 2026-11-03).
#   - 영문 ↔ 한글 표기: "PDRN 에센스" ↔ "피디알엔 에센스 100", "UV" ↔ "유브이", "P-TIOX" ↔ "피티옥스"
#   - 철자: "배리어" ↔ "베리어", "모이스처" ↔ "모이스춰"
#   - 공식명의 일부만 씀: "어성초 세럼" ↔ "어성초 테카 캡슐 세럼 카밍 드롭"
#   - 호수명만 씀: "누디보틀" ↔ "삐아 글로우 틴트 11 누디 보틀"
#   - 붙여 씀: "스킨글로우파운데이션" ↔ "스킨 글로우 래디언트 파운데이션"
#   - 한글 브랜드 표기를 모름: "센슬" · "에이지투웨니스" (data/brand_aliases.json)
#   - 줄임말 · 리뉴얼 전 이름: "장벽천재세럼", "컬러립밤" (data/product_aliases.json, 출처와 함께)
# v1.2 는 후보를 이 표기 차이까지 찾고, 판정 LLM 의 답은 accept_choice_v1_2 로 다시 본다.
# 부분 이름 · 호수명으로 찾은 후보는 이름 점수 90 이라 규칙 확정(95+)이 아니라 판정 LLM 으로 간다.

MATCH_V1_2_VERSION = "match-v1.2"
V12_PARTIAL_SCORE = 90
_TRANSLIT = [("pdrn", "피디알엔"), ("uv", "유브이"), ("egf", "이지에프"), ("ptiox", "피티옥스"), ("bb", "비비"), ("cc", "씨씨")]
_VARIANT = [("배리어", "베리어"), ("모이스처", "모이스춰")]
# v1.2 에서 빠지면 막는 마무리 · 제형 말. v1.1 의 "커버 · 톤업 · 블러 · 샤인" 은 라인 이름에도 쓰여
# ("에센스 커버 팩트", "UV 톤업 베이스") 같은 제품을 막았다. 다른 후보와 가르는 말인지는 rivals 가 본다
FINISH_V12 = {"매트", "글로우", "새틴", "벨벳", "듀이", "스틱", "펜슬", "팁", "팟", "트리플", "리퀴드", "파우더", "젤",
              "matte", "glow", "velvet", "stick", "pencil"}


def canon(text: str) -> str:
    """v1 비교용 정규형. 소문자 · 기호 제거 · 영문 약어 한글화 · 철자 통일 · 공백 제거."""
    t = normalize(_HYPHEN.sub("", (text or "").replace("™", "")))
    for a, b in _TRANSLIT:
        t = re.sub(rf"(?<![a-z]){a}(?![a-z])", b, t)
    for a, b in _VARIANT:
        t = t.replace(a, b)
    return compact(t)


def _segmentable(word: str, parts: list[str]) -> bool:
    """붙여 쓴 말이 후보 이름 단어들을 이어 붙인 것인가 ("스킨글로우파운데이션" = 스킨+글로우+파운데이션)."""
    parts = [x for x in parts if x]
    ok = [True] + [False] * len(word)
    for i in range(len(word)):
        if ok[i]:
            for x in parts:
                if word.startswith(x, i):
                    ok[i + len(x)] = True
    return bool(word) and ok[len(word)]


def score_name_v12(query: str, product: dict, prefixes: dict[str, set[str]]) -> tuple[float, str, list[str]]:
    """score_name + 정규형 비교 + 부분 이름 · 호수명 일치(90)."""
    s, sname, miss = score_name(query, product, prefixes)
    q = core_name(query)
    cq = canon(q)
    core = core_name(product.get("name") or "")
    names = search_names(product, prefixes) or [core]
    words = core.split()
    if len(words) > 1 and words[0] in prefixes.get(product.get("brand") or "", set()):
        names = names + [" ".join(words[1:])]
    # 상품명이 언급 안에 통째로 들어 있는 경우(cs in cq)는 호수 꼬리를 떼기 전 이름으로도 들어 있어야 한다.
    # "에스네이처 아쿠아 365 유브이 선크림" 은 core_name 이 "365 …" 를 호수로 보고 떼어 "아쿠아" 만 남는다.
    # 그 "아쿠아" 가 "아쿠아 오아시스 블루 카밍 앰플" 안에 있다고 같은 제품으로 보면 안 된다
    raw = normalize(_BRACKET.sub(" ", product.get("name") or "")).split()
    fulls = {canon(" ".join(raw))} | ({canon(" ".join(raw[1:]))} if len(raw) > 1 else set())
    for n in names:
        cs = canon(n)
        inside = cs in cq and any(f and f in cq for f in fulls)
        if cq and cs and (cq == cs or inside or (cq in cs and len(cq) >= 0.8 * len(cs))):
            if s < 100:
                s, sname = 100.0, n
        elif cq and cs:
            s = max(s, float(fuzz.ratio(cq, cs)))
    toks = [canon(w) for w in q.split() if canon(w)]
    full = canon(product.get("name") or "")
    dc = distinct_chars(q)
    if toks and ((len(toks) >= 2 and dc >= 2) or dc >= 3) and all(t in full for t in toks):
        s = max(s, float(V12_PARTIAL_SCORE))
    return s, sname, miss


def load_product_aliases(path=None) -> list[dict]:
    """확인된 제품 별칭 (data/product_aliases.json)."""
    import json
    from pathlib import Path

    p = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "product_aliases.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def alias_keys(keys: dict[str, str], brand_aliases: dict[str, set[str]] | None) -> dict[str, str]:
    """브랜드 표기 사전에 확인된 한글 · 계정명 표기를 더한다."""
    out = dict(keys)
    for b, names in (brand_aliases or {}).items():
        for n in names:
            for k in (compact(normalize(n)), _alnum(n)):
                if len(k) >= 2:
                    out[k] = b
    return out


def rank_candidates_v12(mention: dict, products: list[dict], prefixes: dict[str, set[str]], keys: dict[str, str],
                        embed_scores: dict[str, float] | None = None, top_k: int = V1_TOP_K,
                        weak: dict[str, str] | None = None, brand_aliases: dict[str, set[str]] | None = None,
                        product_aliases: list[dict] | None = None) -> tuple[str | None, list[V1Candidate]]:
    """rank_candidates 의 v1.2. 다른 점:

    - 브랜드: 확인된 한글 · 계정명 표기(brand_aliases)도 본다
    - 이름: score_name_v12 (정규형 · 부분 이름 · 호수명)
    - 별칭: product_aliases 에 있는 표현이면 그 상품을 alias 후보(100점)로 맨 앞에 둔다
    - 카테고리를 other 로 뽑은 언급도 그 브랜드 안에서 이름이 거의 같은(90+) 상품은 후보로 둔다
    """
    if mention.get("mention_type") != "product" or not mention.get("product_name"):
        return None, []
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
    byname = {p.get("name"): p for p in products}
    byid = {p["product_id"]: p for p in products}
    qc = canon(core_name(mention["product_name"]))
    qraw = re.sub(r"\s+", "", (mention["product_name"] or "").lower())
    embed_scores = embed_scores or {}
    aliased = []
    for a in product_aliases or []:
        p = byid.get(a.get("product_id") or "") or byname.get(a.get("official_name") or "")
        ac = canon(a["alias"])
        araw = re.sub(r"\s+", "", a["alias"].lower())
        hit = (len(ac) >= 3 and ac in qc) or (not ac and len(araw) >= 3 and araw in qraw)
        if p and hit and (brand is None or brand in a.get("brands", [p.get("brand")])):
            aliased.append(V1Candidate(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                       100.0, embed_scores.get(p["product_id"], 0.0), a["alias"], [], True))
    other = cat not in SCOPE
    pool = [] if (other and brand is None) else [
        p for p in products if (brand is None or p.get("brand") == brand) and (other or p.get("category") == cat)]
    scored = []
    for p in pool:
        s, sname, miss = score_name_v12(mention["product_name"], p, pre)
        scored.append(V1Candidate(p["product_id"], p.get("brand") or "", p.get("name") or "", p.get("category"),
                                  s, embed_scores.get(p["product_id"], 0.0), sname, miss))
    if brand and not other:
        toks = [canon(w) for w in core_name(mention["product_name"]).split() if canon(w)]
        holders = [c for c in scored if toks and all(t in canon(c.name) for t in toks)]
        if len(holders) == 1 and holders[0].name_score < V12_PARTIAL_SCORE:
            holders[0].name_score = float(V12_PARTIAL_SCORE)
    if unknown_brand or other:
        scored = [c for c in scored if c.name_score >= V1_UNKNOWN_BRAND_MIN]
    by_name = sorted(scored, key=lambda c: (-c.name_score, -c.embed_score))[:top_k]
    by_embed = [] if (unknown_brand or other) else sorted(
        (c for c in scored if c.embed_score > 0), key=lambda c: -c.embed_score)[:2]
    merged = list({c.product_id: c for c in by_name + by_embed}.values())
    merged.sort(key=lambda c: (-c.name_score, -c.embed_score))
    seen = {c.product_id for c in aliased}
    out = aliased + [c for c in merged if c.product_id not in seen]
    return (brand or (aliased[0].brand if aliased else None)), out[:top_k]


def auto_decide_v12(mention: dict, brand: str | None, cands: list[V1Candidate]) -> tuple[str, str | None, str]:
    """auto_decide + 별칭 사전 후보는 규칙으로 확정."""
    if mention.get("mention_type") in ("brand_only", "category_only"):
        return mention["mention_type"], None, "제품을 특정할 수 없는 언급"
    if cands and cands[0].alias:
        return MATCHED, cands[0].product_id, f"규칙 확정: 확인된 별칭 '{cands[0].search_name}'"
    return auto_decide(mention, brand, cands)


def accept_choice_v1_2(choice: object, cands: list[V1Candidate], mention: dict,
                       brand_aliases: dict[str, set[str]] | None = None) -> tuple[str, str | None, str]:
    """판정 LLM 의 답을 v1.2 규칙으로 검사한다. (status, product_id, 사유).

    1. 추출명 단어가 후보 이름(호수 · 대괄호 포함 전체)에 있어야 한다. 예외:
       붙여 쓴 말(후보 단어를 이어 붙인 것), 제품 종류 말, 끝에 붙은 호수명(앞부분이 후보 이름에 있을 때),
       4단어 이상 추출명에서 마무리 말이 아닌 한 단어
    2. 후보의 호수명이 추출명에 그대로 있고 같은 호수를 가진 경쟁 후보가 없으면 인정
    3. 후보 이름에만 있는 단어가 마무리 · 제형 말이면 막고, 경쟁 후보(추출명 단어를 모두 가진 같은
       브랜드 · 같은 종류 후보)와 가르는 말이면 막는다
    4. 호수만 다른 쌍둥이 후보가 있으면 고른 호수가 원문에 있어야 한다
    """
    if not isinstance(choice, str):
        return REVIEW, None, "판정 응답 형식이 틀림"
    if choice in ("review", "unmatched"):
        return choice, None, "판정 LLM 이 고르지 않음"
    picked = next((c for c in cands if c.product_id == choice), None)
    if picked is None:
        return REVIEW, None, "후보 밖의 답"
    if picked.alias:
        return MATCHED, choice, "확인된 별칭"
    type_c = {canon(w) for w in TYPE_WORDS}
    finish_c = {canon(w) for w in FINISH_V12}
    ext = [w for w in (canon(x) for x in core_name(mention.get("product_name") or "").split()) if w]
    ext_c = "".join(ext)
    full_c = canon(picked.name)
    pick = [w for w in (canon(x) for x in _v11_words(picked.name)) if w]
    pick_c = "".join(pick)
    said = canon(f"{mention.get('evidence') or ''} {mention.get('brand') or ''}")
    aliases = {canon(a) for a in (brand_aliases or {}).get(picked.brand, set())}

    lacking = [i for i, w in enumerate(ext) if w not in full_c and w not in type_c and not _segmentable(w, pick)]
    if lacking and ext_c not in full_c:
        k = lacking[0]
        head = "".join(ext[:k])
        tail_ok = (k >= 1 and len(head) >= 3 and head in full_c and lacking == list(range(k, len(ext)))
                   and not any(ext[i] in finish_c or ext[i] in type_c for i in lacking))
        ratio_ok = len(ext) >= 4 and len(lacking) == 1 and ext[lacking[0]] not in finish_c
        if not (tail_ok or ratio_ok):
            return REVIEW, None, "추출명 단어가 후보 이름에 없음: " + ", ".join(ext[i] for i in lacking)
    rivals = [c for c in cands if c.product_id != picked.product_id and c.brand == picked.brand
              and c.category == picked.category and all(w in canon(c.name) for w in ext if w not in type_c)]

    shade = [canon(w) for w in normalize(_HYPHEN.sub("", picked.name)).split()
             if canon(w) and canon(w) not in pick_c and not w.isdigit() and _ALNUM_CHAR.search(w)]
    shade_c = "".join(shade)
    if len(shade_c) >= 2 and shade_c in ext_c and not any(shade_c in canon(r.name) for r in rivals):
        return MATCHED, choice, "v1.2 인정: 호수명 일치"

    for w in pick:
        if w in ext_c or w in type_c or w in VERSION_WORDS or w in STOP_WORDS or not _ALNUM_CHAR.search(w):
            continue
        if w in said or w in aliases:
            continue
        if w in finish_c:
            return REVIEW, None, f"마무리 · 제형 말이 빠짐: {w}"
        if any(w not in canon(r.name) for r in rivals):
            return REVIEW, None, f"같은 브랜드 다른 후보와 가르는 말이 빠짐: {w}"
    twins = [r for r in rivals if [canon(x) for x in _v11_words(r.name)] == pick]
    if twins and not (len(shade_c) >= 2 and shade_c in said):
        return REVIEW, None, "호수만 다른 후보가 있는데 고른 호수가 원문에 없음"
    return MATCHED, choice, "v1.2 인정"


def dedupe_hashtags(rows: list[dict], names: dict[str, str]) -> None:
    """같은 게시물에서 해시태그로 한 번 더 적힌 언급은 이미 잡은 언급과 같은 제품으로 본다.

    브랜드 없이 '#…' 로만 적힌 product 언급이 못 잡혔고, 같은 게시물에 matched 언급이 있으며
    그 상품명과 정규형 부분 일치(partial_ratio)가 90 이상이면 그 상품으로 둔다(method = "hashtag").
    """
    hits = [(r["product_id"], canon(names.get(r["product_id"], ""))) for r in rows if r["status"] == MATCHED]
    for r in rows:
        m = r["mention"]
        if r["status"] == MATCHED or m.get("brand") or not (m.get("evidence") or "").lstrip().startswith("#"):
            continue
        q = canon(m.get("product_name") or "")
        qs = [q] + [q[:-len(canon(t))] for t in TYPE_WORDS if q.endswith(canon(t)) and len(q) - len(canon(t)) >= 4]
        best = max(((fuzz.partial_ratio(x, n), pid) for pid, n in hits if n for x in qs), default=(0, None))
        if len(q) >= 4 and best[0] >= 90:
            r.update(status=MATCHED, product_id=best[1], method="hashtag", reason="같은 게시물의 해시태그 중복")
