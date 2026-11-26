"""인스타 캡션에서 성분 · 피부 고민 키워드를 찾는다 (규칙, LLM 없음).

트렌드를 제품 단위로 세려면 캡션 속 제품을 상품 마스터와 이어야 하는데, 표현이
제각각이라 정확도를 보장할 수 없었다. 성분(PDRN · 시카 …)과 고민(보습 · 장벽 …)은
표기가 몇 가지로 정해져 있어 사전으로 거의 틀리지 않고 찾을 수 있다.

판정은 게시물 단위 이진이다. 한 캡션에 같은 키워드가 여러 번 나와도 한 번이다.
근거로 어느 줄의 어떤 표기에 걸렸는지 함께 돌려준다.

- @멘션은 지우고 본다. 계정명 속 단어(@cica_official)가 걸리지 않게 한다.
- 해시태그는 남긴다. #pdrn앰플 도 키워드 신호다.
- 헤어 · 바디 제품을 말하는 줄은 건너뛴다(사전의 skip_line_words). "판테놀 캡슐
  트리트먼트"는 홈 트렌드 범위(베이스 · 선 · 립 · 스킨케어)가 아니다.
- word_forms 의 짧은 영문(aha · bha · pha)은 앞뒤가 영문 · 한글이 아닐 때만 잡는다.
- exclude 의 말은 그 키워드를 찾기 전에 지운다("시카고" ≠ 시카).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KEYWORD_VERSION = "keyword-v1"
DICT_PATH = Path(__file__).resolve().parents[1] / "data" / "trend_keywords.json"

INGREDIENT = "ingredient"
CONCERN = "concern"

_MENTION = re.compile(r"@[\w.]+")


@dataclass(frozen=True)
class Keyword:
    id: str
    label: str
    group: str
    forms: tuple[str, ...]
    word_forms: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    product_ingredients: tuple[str, ...] = ()
    product_concerns: tuple[str, ...] = ()
    product_name_forms: tuple[str, ...] = ()


@dataclass
class KeywordDictionary:
    keywords: list[Keyword]
    skip_line_words: tuple[str, ...] = ()
    version: str = ""
    by_id: dict[str, Keyword] = field(default_factory=dict)

    def __post_init__(self):
        self.by_id = {k.id: k for k in self.keywords}


@dataclass(frozen=True)
class KeywordHit:
    keyword_id: str
    group: str
    form: str
    line: str


def load_keywords(path: Path = DICT_PATH) -> KeywordDictionary:
    raw = json.loads(path.read_text(encoding="utf-8"))
    kws = []
    for k in raw["keywords"]:
        kws.append(Keyword(
            id=k["id"], label=k["label"], group=k["group"],
            forms=tuple(f.lower() for f in k["forms"]),
            word_forms=tuple(f.lower() for f in k.get("word_forms", [])),
            exclude=tuple(f.lower() for f in k.get("exclude", [])),
            product_ingredients=tuple(k.get("product_ingredients", [])),
            product_concerns=tuple(k.get("product_concerns", [])),
            product_name_forms=tuple(f.lower() for f in k.get("product_name_forms", [])),
        ))
    ids = [k.id for k in kws]
    if len(ids) != len(set(ids)):
        raise ValueError("키워드 id 가 겹친다")
    if any(k.group not in (INGREDIENT, CONCERN) for k in kws):
        raise ValueError("group 은 ingredient · concern 둘 중 하나다")
    return KeywordDictionary(kws, tuple(w.lower() for w in raw.get("skip_line_words", [])), raw.get("version", ""))


def _word_re(form: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z가-힣]){re.escape(form)}(?![a-z가-힣])")


def find_form(text: str, kw: Keyword) -> str | None:
    """text(소문자) 에서 kw 의 표기를 찾아 처음 걸린 표기를 돌려준다."""
    for ex in kw.exclude:
        text = text.replace(ex, " ")
    for f in kw.forms:
        if f in kw.word_forms:
            if _word_re(f).search(text):
                return f
        elif f in text:
            return f
    return None


def _skip_line(line: str, words: tuple[str, ...]) -> bool:
    """헤어 · 바디 제품을 말하는 줄인가. 영문은 단어 단위로 본다("everybody" 는 body 가 아니다)."""
    for w in words:
        if w.isascii():
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", line):
                return True
        elif w in line:
            return True
    return False


def extract_keywords(caption: str | None, d: KeywordDictionary) -> list[KeywordHit]:
    """캡션 하나 → 걸린 키워드 목록 (사전 순서, 키워드마다 하나)."""
    text = _MENTION.sub(" ", caption or "").lower()
    lines = [ln for ln in text.splitlines() if ln.strip() and not _skip_line(ln, d.skip_line_words)]
    hits = []
    for kw in d.keywords:
        for ln in lines:
            f = find_form(ln, kw)
            if f:
                hits.append(KeywordHit(kw.id, kw.group, f, ln.strip()[:120]))
                break
    return hits
