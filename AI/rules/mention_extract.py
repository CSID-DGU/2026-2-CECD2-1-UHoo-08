"""캡션 → 브랜드 · 제품명 추출 (규칙, LLM 없음, 같은 입력이면 같은 결과).

ProductMatcher v2 의 ① 단계. 캡션에 적힌 표현을 그대로 뽑는다. 정식명으로 바꾸지 않는다(그건 DB 매칭 · 쇼핑 검색이 한다).
범위(base · sun · lip · skincare) 밖 화장품도 뽑고 category 로 표시만 한다. DB 매칭에서 범위 밖을 뺀다.
쇼핑 검색어는 Mention.query = "브랜드 제품명".

찾는 곳 (source)
  structured  "① 브랜드 - 제품명", "브랜드 : 제품명" 처럼 한 줄이 구분자로 브랜드 / 제품명으로 나뉜 줄
  list        "✅ 센슈얼 틴티드 샤인 립 세럼 (323 체리온탑)" 처럼 목록 기호로 시작하는 짧은 제품 줄
  text        본문 문장에서 제품 종류 말(틴트 · 세럼 …)로 끝나는 명사구. 바로 앞에 브랜드 표기가 있으면 그 브랜드
  hashtag     #브랜드제품명 · #제품명 (종류 말로 끝나는 것)
브랜드가 바로 붙어 있지 않으면 글 전체에 브랜드가 하나뿐일 때만 그 브랜드를 쓴다(brand_from = context). 아니면 비운다.

게시물 분류 (post_kind) — 뷰티 무관 · 언급 없음 거르기
  product     제품을 하나 이상 뽑음
  beauty      화장품 브랜드 표기나 종류 말은 나오지만 제품을 특정할 수 없음 (브랜드만 · 종류만)
  non_beauty  둘 다 없음 (일상 · 패션 · 여행 …)

브랜드 사전은 밖에서 받는다(build_brand_lexicon). 사전에 없는 브랜드는 structured 줄의 앞부분과 공식 계정명(_official 등)으로 찾는다.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

EXTRACT_RULE_VERSION = "extract-rule-v0.1"

SCOPE = {"base", "sun", "lip", "skincare"}

# 제품 종류 말 → category. 긴 말부터 본다("립라이너" 가 "라이너" 보다 먼저)
_TYPE_TABLE = {
    "lip": "립스틱 립밤 립글로스 립글로즈 립글라스 립오일 립라이너 립펜슬 립세럼 립스테인 립글레이즈 립플럼퍼 립틴트 립마스크 립락커 "
           "틴트 글로스 락커 루즈 스틱 tint gloss lipstick balm",
    "sun": "선크림 선스틱 선쿠션 선세럼 선에센스 선스크린 선로션 선젤 선밀크 선미스트 썬크림 썬스틱 썬쿠션 썬스크린 sunscreen",
    "base": "쿠션 파운데이션 컨실러 프라이머 팩트 파우더 픽서 프렙 비비크림 씨씨크림 비비 베이스 코렉터 cushion foundation concealer primer",
    "skincare": "토너 스킨 세럼 앰플 에센스 크림 로션 미스트 패드 부스터 수분크림 아이크림 젤크림 겔크림 오일 밤 캡슐 젤리 패치 "
                "toner serum ampoule essence cream lotion",
    "eye": "아이팔레트 팔레트 섀도우 쉐도우 아이섀도우 아이라이너 라이너 마스카라 아이브로우 브로우 아이래쉬 속눈썹 글리터 palette mascara",
    "cheek": "블러셔 블러쉬 블러시 치크 하이라이터 쉐딩 컨투어 치크칩 립앤치크 blush cheek",
    "cleansing": "클렌저 클렌징폼 클렌징오일 클렌징밤 클렌징 폼클렌저 솝 비누 필링 cleanser",
    "mask": "마스크팩 마스크 시트팩 팩 mask",
    "hair": "샴푸 트리트먼트 헤어오일 헤어팩 shampoo",
    "body": "바디로션 바디워시 바디크림 핸드크림 바디스크럽",
    "nail": "큐티클오일 네일",
    "tool": "퍼프 브러쉬 브러시 스펀지",
}
TYPE_WORDS: dict[str, str] = {}
for _cat, _words in _TYPE_TABLE.items():
    for _w in _words.split():
        TYPE_WORDS.setdefault(_w, _cat)
_TYPES_BY_LEN = sorted(TYPE_WORDS, key=len, reverse=True)
_ONE_CHAR = {"밤", "팩"}        # 한 글자 종류 말은 다른 말에 붙어 있을 때만 (글로이밤 · 치크 팟은 앞 단어와 묶임)
_NOT_PRODUCT_TAIL = ("추천", "맛집", "템", "추천템", "리뷰", "후기", "꿀템", "순위", "랭킹", "이벤트", "세일", "모음", "조합", "메이크업",
                     "추천해요", "맛", "러버", "덕후", "중독")
# 종류 말만 있거나 종류 말 + 이것들뿐이면 제품을 특정할 수 없다
_GENERIC = {"립", "베이스", "스킨", "오일", "크림", "세럼", "쿠션", "틴트", "팩트", "파우더", "토너", "패드", "앰플", "에센스", "마스크",
            "수분", "진정", "보습", "톤업", "커버", "매트", "글로우", "촉촉", "데일리", "신상", "인생", "최애", "선", "썬", "컬러", "미니",
            "본품", "리필", "단품", "기획", "세트", "신제품", "제품", "화잘먹", "가을", "겨울", "여름", "봄", "환절기", "건성", "지성",
            "민감성", "수부지", "모공", "장벽"}
# 제품명에 들어가지 않는 말. 이 말이 나오면 이름을 거기서 끊는다
_STOP = {"이", "그", "저", "요", "제", "내", "나", "진짜", "너무", "완전", "정말", "특히", "신제품", "신상", "최애", "요즘", "이번", "이번엔",
         "오늘", "추천", "인생", "역대급", "제일", "가장", "꼭", "무조건", "그냥", "바로", "다", "또", "대박", "이거", "요거", "이건", "그리고",
         "및", "event", "이벤트", "광고", "협찬", "증정", "할인", "특가", "올영", "올리브영", "쿠팡", "무신사", "출시", "런칭", "단독", "한정",
         "한정판", "기획", "기획세트", "세트", "단품", "정품", "본품", "리필", "new", "신규", "사은품", "구매시", "구매", "+", "&", "x", "×",
         "써본", "쓰는", "바른", "사용한", "제가", "저는", "우리", "같은", "같이", "함께", "위에", "위", "아래", "전", "후", "중", "중에",
         "중에서", "컬러", "호", "색", "향", "지금", "드디어", "처음", "먼저", "다음", "마지막", "하나", "두", "세", "네", "개", "종",
         "피부", "사진", "속", "저의", "나의", "애정템", "스테디셀러", "크기", "음영", "느낌", "버전", "라인", "시리즈", "모든", "전부"}
_LEFT_STOP = {"방법", "경품", "기간", "구매", "후기", "이벤트", "혜택", "증정", "일정", "장소", "제품", "컬러", "가격", "참여", "발표", "당첨",
              "당첨자", "할인", "링크", "정보", "기준", "용량", "사용법", "주의", "효과", "성분", "특징", "장점", "단점", "팁", "날짜", "시간",
              "브랜드", "추천", "총평", "결론", "요약", "구성", "기획", "세트", "구매처", "판매처", "택배", "배송", "pick", "best", "top"}
# 수식 · 서술 어미. 제품명 안에 오지 않는다 ("촉촉한", "올라오는", "잘썼으면", "좋아요")
_MODIFIER_END = re.compile(r"(?:한|운|던|할|게|고|서|며|해|요|다|죠|네|면|니|까|데|든|는|은|된|진|춘|든|준|히|들|로운|스런|스러운|같은|있는|없는|하는|되는|수록)$")
_PARTICLE = re.compile(r"(?:을|를|이|가|은|는|의|에서|에|로|으로|도|만|까지|부터|이랑|랑|과|와|처럼|보다|이에요|예요|입니다|이다|이랑)$")

_CIRCLED = re.compile(r"[①-⑳⓪❶-❿➀-➓]|[0-9]️?⃣|[\U0001F51F]")
_BULLET = re.compile(r"^\s*[\-–—•·*>‐-―←-⇿⌀-⏿─-➿⤀-⯿️‍\U0001F000-\U0001FAFF]+")
_NUMBERED = re.compile(r"^\s*(?:\d{1,2}[.)]\s+|\(\d{1,2}\)\s*|[A-Za-z][.)]\s+)")
_SEP = re.compile(r"\s+[-–—:|]\s+|\s*[–—|]\s*|\s+-(?=\S)|(?<=\S)-\s+")
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}|<[^>]*>|‘[^’]*’|“[^”]*”")
_PRICE = re.compile(r"\d[\d,]*\s*원|\d+\s*%|(?:→|->|>).*$|\d+\s*(?:ml|g|매|colors?|종|개입|입)\b", re.IGNORECASE)
_KEEP = re.compile(r"[^0-9A-Za-z가-힣&+.'\-\s:]")
_HASHTAG = re.compile(r"#([0-9A-Za-z가-힣_&+]+)")
_HANDLE = re.compile(r"(?<![0-9a-z_.])@?([a-z0-9][a-z0-9_.]{2,})_(official|kr|korea|global|jp|makeup|beauty|cosmetics?|skin|official_jp)(?![a-z0-9_])")
_COLLAB = re.compile(r"\s+[xX×]\s+")
_ODD = re.compile(r"^\d{1,2}(?:[./]\d{1,2})?$|^\d[\d,]{3,}|^\d+\+\d+|^\+|명$|원$|일$|월$|시$|분$|\.\.|…")


def _clean(text: str) -> str:
    t = _CIRCLED.sub(" ", text or "")
    t = unicodedata.normalize("NFKC", t)
    return t.replace("’", "'").replace("‘", "'")


def _bare(word: str) -> str:
    return word.strip(".,!?~'\"`:;·…()[]{}<>").strip()


def _drop_particle(word: str) -> tuple[str, bool]:
    """'세럼을' → ('세럼', True). 종류 말이나 브랜드 뒤에 붙은 조사를 뗀다."""
    m = _PARTICLE.search(word)
    if m and len(word) - len(m.group(0)) >= 2:
        return word[: m.start()], True
    return word, False


def type_of(word: str) -> tuple[str | None, str | None]:
    """단어가 종류 말로 끝나면 (종류 말, category)."""
    w = _bare(word).lower()
    w2, _ = _drop_particle(w)
    for cand in (w, w2):
        for tw in _TYPES_BY_LEN:
            if not cand.endswith(tw):
                continue
            if tw in _ONE_CHAR and len(cand) == 1:
                continue
            if any(cand.endswith(t) for t in _NOT_PRODUCT_TAIL):
                return None, None
            return tw, TYPE_WORDS[tw]
    return None, None


def category_of(name: str) -> str | None:
    """제품명의 category. 마지막 두 단어를 붙인 말("립 세럼" → 립세럼)부터 본다."""
    ws = name.split()
    if len(ws) >= 2:
        tw, cat = type_of(ws[-2] + ws[-1])
        if tw and len(tw) > len(type_of(ws[-1])[0] or ""):
            return cat
    for w in reversed(ws):
        tw, cat = type_of(w)
        if cat:
            return cat
    return None


@dataclass
class Mention:
    brand: str | None          # 브랜드 (사전에 있으면 대표 표기, 없으면 캡션 표기)
    name: str                  # 캡션에 적힌 제품명 (브랜드 · 호수 · 가격 · 괄호 제외)
    category: str | None
    source: str                # structured · list · text · hashtag
    evidence: str              # 근거가 된 줄 (원문)
    brand_from: str = "none"   # adjacent(바로 붙음) · lexicon · handle · context(글의 유일한 브랜드) · none
    variant: str | None = None

    @property
    def in_scope(self) -> bool:
        return self.category in SCOPE

    @property
    def query(self) -> str:
        """쇼핑 검색어 '브랜드 제품명'."""
        return f"{self.brand} {self.name}".strip() if self.brand else self.name


@dataclass
class Extraction:
    post_kind: str
    mentions: list[Mention]
    brands_seen: list[str] = field(default_factory=list)
    type_words_seen: list[str] = field(default_factory=list)
    version: str = EXTRACT_RULE_VERSION


@dataclass
class BrandLexicon:
    """표기(소문자 · 공백 없앰) → 대표 표기."""
    surfaces: dict[str, str]

    def find(self, text: str) -> list[tuple[int, int, str]]:
        """text 안의 브랜드 표기 위치 [(시작, 끝, 대표 표기)]. 긴 표기부터, 겹치면 먼저 잡힌 것."""
        low = text.lower()
        hits: list[tuple[int, int, str]] = []
        taken = [False] * (len(text) + 1)
        for surf in sorted(self.surfaces, key=len, reverse=True):
            start = 0
            while (i := low.find(surf, start)) >= 0:
                j = i + len(surf)
                start = i + 1
                if any(taken[i:j]) or not _boundary_ok(text, i, j, surf):
                    continue
                for k in range(i, j):
                    taken[k] = True
                hits.append((i, j, self.surfaces[surf]))
        return sorted(hits)

    def exact(self, word: str) -> str | None:
        w = _bare(word).lower().replace(" ", "")
        if w in self.surfaces:
            return self.surfaces[w]
        w2, _ = _drop_particle(w)
        return self.surfaces.get(w2)


def _boundary_ok(text: str, i: int, j: int, surf: str) -> bool:
    before = text[i - 1] if i > 0 else " "
    after = text[j] if j < len(text) else " "
    if re.match(r"[a-z0-9]", surf):
        return not re.match(r"[A-Za-z0-9]", before) and not re.match(r"[A-Za-z]", after)
    if re.match(r"[가-힣]", before):
        return False
    # 두 글자 이하 한글 브랜드("맥", "구달")는 뒤에 한글이 바로 붙으면 다른 말이다(맥주). 조사만 허용
    if len(surf) <= 2 and re.match(r"[가-힣]", after):
        return bool(re.match(r"(?:의|에|는|은|이|가|를|을|도|랑|과|와|x)", text[j:j + 1]))
    return True


def build_brand_lexicon(products: list[dict], brand_aliases: dict[str, set[str]] | None = None,
                        owned: dict[str, list[str]] | None = None) -> BrandLexicon:
    """DB 브랜드명(영문) · 확인된 브랜드 표기(brand_aliases · brand_names_ko) · 계정 운영 브랜드.

    상품명 첫 단어로 브랜드 표기를 짐작하지 않는다. "프로"(ESPOIR) · "맑은"(GOODAL) 처럼 라인명이 브랜드로 들어갔다.
    """
    surf: dict[str, str] = {}

    def add(s: str, canon: str):
        k = (s or "").lower().replace(" ", "")
        if len(k) >= 2 or re.fullmatch(r"[가-힣]", k or "x"):
            surf.setdefault(k, canon)

    for p in products:
        if p.get("brand"):
            add(p["brand"], p["brand"])
    for b, names in (brand_aliases or {}).items():
        for n in names:
            add(n, b)
    for names in (owned or {}).values():
        for n in names or []:
            add(n, names[0])
    return BrandLexicon({k: v for k, v in surf.items() if len(k) >= 1})


def _name_like(word: str) -> bool:
    """제품명 안에 들어갈 수 있는 단어인가."""
    w = _bare(word)
    if not w or w.lower() in _STOP or _ODD.search(word):
        return False
    if re.fullmatch(r"[0-9A-Za-z+&.\-]+", w):
        return True
    stem, had = _drop_particle(w)
    if had:
        return False        # "쿠션에", "브랜드의" — 조사가 붙은 말은 이름 안에 오지 않는다
    if type_of(w)[0]:
        return True
    return not _MODIFIER_END.search(w) or len(w) <= 1


def _tidy(raw: str) -> tuple[str, str | None]:
    """괄호 · 가격 · 용량을 떼고 (이름, 괄호 속 호수 · 옵션)."""
    m = re.search(r"\(([^)]*)\)", raw)
    variant = m.group(1).strip() if m and m.group(1).strip() else None
    t = _PAREN.sub(" ", raw)
    t = _PRICE.sub(" ", t)
    t = _KEEP.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip(" -.:'")
    return t, variant


def _specific(name: str) -> bool:
    """종류 말 하나뿐이거나 일반어 + 종류 말이면 제품을 특정할 수 없다."""
    ws = [w for w in name.split() if w]
    if not ws or category_of(name) is None:
        return False
    rest = []
    for w in ws:
        tw, _ = type_of(w)
        core = _bare(w).lower()
        if tw and core != tw:
            core = core[: -len(tw)]
            if core and core not in _GENERIC:
                rest.append(core)
        elif not tw and core not in _GENERIC and core.lower() not in _STOP:
            rest.append(core)
    return sum(len(x) for x in rest) >= 2


def extract(caption: str, lexicon: BrandLexicon, owned_brands: list[str] | None = None) -> Extraction:
    cap = _clean(caption)
    out: list[Mention] = []

    # 글 전체에서 보이는 브랜드 (사전 · 공식 계정명)
    brands_seen: list[str] = []
    for _, _, b in lexicon.find(cap):
        if b not in brands_seen:
            brands_seen.append(b)
    handle_brands = []
    for h, _ in _HANDLE.findall(cap.lower()):
        hit = lexicon.find(h)
        b = (lexicon.exact(h) or lexicon.exact(h.replace("_", "").replace(".", ""))
             or (hit[0][2] if hit and hit[0][0] == 0 and hit[0][1] - hit[0][0] >= 3 else None) or h)
        handle_brands.append(b)
        if b not in brands_seen:
            brands_seen.append(b)
    context = brands_seen[0] if len(brands_seen) == 1 else None

    def strip_brand(name: str, brand: str | None) -> tuple[str, str | None, str]:
        """이름 앞에 브랜드 표기가 붙어 있으면 떼고 그 브랜드를 쓴다 ("투쿨포스쿨 무드 스위치 팔레트")."""
        ws = name.split()
        how = ""
        while ws:
            b = lexicon.exact(ws[0])
            if b is None and brand and _bare(ws[0]).lower().replace(" ", "") == str(brand).lower().replace(" ", ""):
                b = brand
            if b is None or len(ws) == 1:
                break
            brand, how = b, "adjacent"
            ws = ws[1:]
        return " ".join(ws), brand, how

    def push(brand, brand_from, raw_name, source, evidence):
        name, variant = _tidy(raw_name)
        name, b2, how = strip_brand(name, brand)
        if b2 != brand:
            brand, brand_from = b2, how or brand_from
        # 구분자 줄에서 브랜드가 분명하면 종류 말뿐인 이름도 받는다 ("퓌 - 치크칩")
        explicit = source == "structured" and brand and len(name.replace(" ", "")) >= 3 and category_of(name)
        if not (_specific(name) or explicit) or len(name.split()) > 9:
            return
        out.append(Mention(brand, name, category_of(name), source, evidence.strip(), brand_from if brand else "none", variant))

    for raw in cap.splitlines():
        if not raw.strip():
            continue
        body = _HASHTAG.sub(" ", raw)
        is_list = bool(_BULLET.match(body) or _NUMBERED.match(body))
        core = _NUMBERED.sub("", _BULLET.sub("", body)).strip()
        if not core:
            continue
        if re.match(r"^\s*\d{1,3}\s+[^\d\s]", body) and len(core.split()) <= 4:
            continue        # "13 라일락 크림" — 컬러 호수 목록 줄

        # structured: "브랜드 - 제품명"
        parts = _SEP.split(core, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            left = _COLLAB.split(_PAREN.sub(" ", parts[0]).strip())[0]
            left = re.sub(r"[^0-9A-Za-z가-힣&+.' ]", "", left).strip()
            known = lexicon.exact(left)
            left_ok = known or (left and len(left.split()) <= 2 and not re.search(r"\d", left)
                                and not any(w.lower() in _LEFT_STOP or w.lower() in _STOP for w in left.split())
                                and not type_of(left)[0] and not _MODIFIER_END.search(left.split()[-1]))
            if left_ok:
                pieces = [p for p in re.split(r"\s*[,/]\s*|\s+\+\s+|\s+그리고\s+", parts[1]) if p.strip()]
                got = False
                for piece in pieces:
                    before = len(out)
                    push(known or left, "lexicon" if known else "structured", piece, "structured", raw)
                    got = got or len(out) > before
                if got:
                    continue

        # list: 목록 기호로 시작하는 짧은 제품 줄 (괄호 · 가격 뗀 뒤 9단어 이하, 서술어 없음)
        if is_list:
            name, _ = _tidy(core)
            ws = name.split()
            # 종류 말 단어 수. "립 세럼" 처럼 붙여 한 종류 말이 되는 두 단어는 하나로 센다
            n_types = sum(1 for i, w in enumerate(ws) if type_of(w)[0]
                          and not (i + 1 < len(ws) and (ws[i] + ws[i + 1]) in TYPE_WORDS))
            if ws and len(ws) <= 9 and n_types == 1 and type_of(ws[-1])[0] and all(_name_like(w) for w in ws):
                hit = lexicon.find(name)
                b = hit[0][2] if hit and hit[0][0] == 0 else context
                push(b, "adjacent" if hit and hit[0][0] == 0 else "context", core, "list", raw)
                continue

        # text: 종류 말로 끝나는 명사구를 뒤에서부터 모은다 (괄호 · 가격 · 용량은 먼저 뗀다)
        words = _tidy(core)[0].split()
        k = 0
        while k < len(words):
            tw, _ = type_of(words[k])
            if not tw:
                k += 1
                continue
            last, had_particle = _drop_particle(_bare(words[k]))
            name_ws = [last]
            brand, how = None, ""
            m = k - 1
            while m >= 0 and len(name_ws) < 6:
                w = _bare(words[m])
                b = lexicon.exact(w)
                if b:
                    brand, how = b, "adjacent"
                    break
                if w.lower() in ("x", "×") and m >= 1 and lexicon.exact(words[m - 1]):
                    m -= 1          # "유리아쥬 X 롬앤 컬러립밤" → 롬앤 이 바로 앞 브랜드
                    continue
                if not _name_like(w):
                    break
                name_ws.insert(0, w)
                m -= 1
            if brand is None and context:
                brand, how = context, "context"
            push(brand, how or "none", " ".join(name_ws), "text", raw)
            k += 1

    # hashtag
    for tag in _HASHTAG.findall(cap):
        t = tag.replace("_", "")
        hits = lexicon.find(t)
        tw, _ = type_of(t)
        if not tw:
            continue
        if hits and hits[0][0] == 0 and len(t) > hits[0][1]:
            push(hits[0][2], "adjacent", t[hits[0][1]:], "hashtag", "#" + tag)
        elif not hits and len(t) >= len(tw) + 2:
            push(context, "context" if context else "none", t, "hashtag", "#" + tag)

    mentions = _dedupe(out)
    types_seen = sorted({tw for w in re.split(r"[\s#]+", cap) if (tw := type_of(w)[0])})
    if mentions:
        kind = "product"
    elif brands_seen or types_seen:
        kind = "beauty"
    else:
        kind = "non_beauty"
    return Extraction(kind, mentions, brands_seen, types_seen)


_ORDER = {"structured": 0, "list": 1, "text": 2, "hashtag": 3}


def _key(m: Mention) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", m.name.lower())


def _dedupe(ms: list[Mention]) -> list[Mention]:
    """같은 제품을 여러 곳에서 뽑았으면 하나로. 붙여 쓴 해시태그가 본문 표기와 같으면 본문 쪽을 남긴다.

    한쪽 이름이 다른 쪽 이름을 포함하면 같은 제품으로 본다("젤핏글로스" ⊂ "젤핏 글로스"). 브랜드가 다르면 다른 제품이다.
    """
    kept: list[Mention] = []
    for m in sorted(ms, key=lambda x: _ORDER[x.source]):
        k = _key(m)
        dup = next((x for x in kept if (k == _key(x) or k in _key(x) or _key(x) in k)
                    and (x.brand == m.brand or not m.brand or not x.brand)), None)
        if dup is None:
            kept.append(m)
            continue
        if _ORDER[m.source] == _ORDER[dup.source] and len(k) > len(_key(dup)) and k.endswith(_key(dup)[-2:]):
            dup.name, dup.evidence, dup.category = m.name, m.evidence, m.category
        if not dup.brand and m.brand:
            dup.brand, dup.brand_from = m.brand, m.brand_from
    return kept
