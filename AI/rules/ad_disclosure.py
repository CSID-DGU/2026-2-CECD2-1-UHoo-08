"""인스타 캡션의 광고 여부 1차 판정.

캡션에 적힌 표기만 보고 광고 / 광고 아님 / 모름 셋 중 하나를 낸다. 모름은
2차 LLM 이 다시 본다. 확실한 것은 여기서 끝내야 LLM 호출이 줄고, LLM 이
"#광고"가 붙은 글을 광고 아님으로 보는 일도 없다.

판정 기준은 eval/prompts/trend_ad_v1.md 에 있다. 경제적 이해관계가 있으면
광고다. 유료광고·협찬뿐 아니라 제품제공, 본인 브랜드 홍보, 공구·링크 DM 도
광고로 센다.

표기 형태가 제각각이다. "#광고" 말고도 "*광고", "광고*", "(광고)", "[광고]",
"#유료광고", 문장 끝의 "광고 skin1004_korea", "(단순선물제공)",
"제품 무료 제공 (노출 의무 없음)" 이 실제 캡션에 있다. 반대로 "(광고 아님)"
처럼 광고라는 말이 들어가도 광고가 아닌 글이 있다.

범례형 캡션은 따로 본다. "📘 직접 구매 / 📗 제품무상제공 / 📙 유료광고" 를
먼저 적고 제품마다 아이콘을 붙이는 형식이라, 범례 줄의 "유료광고" 만 보고
광고로 보면 전부 직접 산 제품인 글도 광고가 된다. 범례 줄은 빼고, 본문에
제공·광고 아이콘이 쓰였는지를 본다.
"""
from __future__ import annotations

import re

RULE_VERSION = "ad-rule-v1"

AD = "ad"
ORGANIC = "organic"
UNSURE = "unsure"

_I = re.IGNORECASE | re.MULTILINE

# 범례 줄: 아이콘 하나 + 뜻. 아이콘은 글자·숫자가 아닌 기호다
_LEGEND_LINE = re.compile(r"^[ \t]*([^\w\s#@(\[]{1,3})[ \t]*(.+)$", re.MULTILINE)
_LEGEND_PURCHASE = re.compile(r"직접\s*구매|내돈내산")
_LEGEND_SPONSORED = re.compile(r"무상\s*제공|제품\s*제공|무료\s*제공|선물|협찬|유료\s*광고|원고료")

# 판정 근거 이름 → 패턴. 이름은 hits 에 그대로 남는다
_DISCLOSURE = {
    "hashtag": r"#\s*(?:유료\s*)?광고(?!\s*(?:아님|아니|x\b))",
    "bracket": r"[(\[]\s*광고\s*[)\]]",
    "asterisk": r"\*\s*광고|광고\s*\*",
    "line": r"^[ \t]*광고[ \t]*(?:[@\w.]+)?[ \t]*$",
    "sponsored": r"#\s*협찬|[(\[]\s*협찬\s*[)\]]|협찬\s*(?:받|제품|후)",
    "paid": r"유료\s*광고|원고료",
}
_GIFTED = {
    "hashtag": r"#\s*제품\s*제공",
    "bracket": r"[(\[]\s*제품\s*제공\s*[)\]]",
    "gift": r"단순\s*선물|선물\s*제공",
    "free": r"(?:무료|무상)\s*제공",
    "gift_tag": r"(?:^|\s)#🎁",
}
_AFFILIATE = {
    "group_buy": r"공구|공동\s*구매",
    "link_dm": r"링크[^\n]{0,15}(?:보내|발송|드려|드릴)|링크\s*필요[^\n]{0,20}댓글|댓글[^\n]{0,20}링크",
    "buy_link": r"(?:구매|할인)\s*링크",
}
# 프로필 링크는 유튜브 안내에도 쓴다. 구매를 권하는 말이 가까이 있을 때만 본다.
# "겨우 구매했어요" 는 권하는 말이 아니라 직접 산 이야기다
_PROFILE_LINK = re.compile(r"프로필\s*링크")
_PROFILE_BUY = re.compile(r"구매(?!했)|할인|특가|만나보|주문")
_PROFILE_WINDOW = 40

_NEGATION = {
    "not_ad": r"광고\s*(?:아님|아니에요|아닙니다|아니고|x\b)",
    "own_purchase": r"내돈내산|직접\s*구매",
}
# 이것만 있으면 광고라고 단정하지 않는다. 2차에서 본다
_COMMERCIAL = {
    "sale": r"특가|오특|세일|런칭\s*가|할인\s*가|최저가",
    "discount": r"\d+\s*%\s*(?:할인|off)|[\d,]+\s*원\s*(?:→|->|>|⤏)\s*[\d,]+\s*원|쿠폰",
    "event": r"이벤트|증정|추첨|당첨",
    "store_open": r"선물하기|입점|재입고|당일\s*출고",
}


def _compile(table: dict[str, str]) -> dict[str, re.Pattern]:
    return {name: re.compile(p, _I) for name, p in table.items()}


_RULES = {
    "disclosure": _compile(_DISCLOSURE),
    "gifted": _compile(_GIFTED),
    "affiliate": _compile(_AFFILIATE),
    "negation": _compile(_NEGATION),
    "commercial": _compile(_COMMERCIAL),
}


def split_legend(caption: str) -> tuple[str, dict[str, str]]:
    """범례 줄을 떼어 낸다. (범례를 뺀 본문, 아이콘 → 'purchase' | 'sponsored')

    아이콘 하나에 뜻 하나인 줄이 두 개 이상이고, 그중 하나가 직접 구매일 때만
    범례로 본다. "🎁 증정 이벤트" 한 줄을 범례로 오인하지 않기 위해서다.
    """
    legend: dict[str, str] = {}
    spans = []
    for m in _LEGEND_LINE.finditer(caption):
        icon, meaning = m.group(1), m.group(2)
        if _LEGEND_PURCHASE.search(meaning) and len(meaning) < 30:
            legend[icon] = "purchase"
        elif _LEGEND_SPONSORED.search(meaning) and len(meaning) < 30:
            legend[icon] = "sponsored"
        else:
            continue
        spans.append(m.span())
    if len(legend) < 2 or "purchase" not in legend.values():
        return caption, {}
    body = caption
    for start, end in reversed(spans):
        body = body[:start] + body[end:]
    return body, legend


def _find(group: str, text: str) -> list[dict]:
    hits = []
    for name, pattern in _RULES[group].items():
        m = pattern.search(text)
        if m:
            hits.append({"rule": f"{group}.{name}", "text": m.group(0).strip()})
    return hits


def _profile_link(text: str) -> list[dict]:
    for m in _PROFILE_LINK.finditer(text):
        around = text[max(0, m.start() - _PROFILE_WINDOW): m.end() + _PROFILE_WINDOW]
        if _PROFILE_BUY.search(around):
            return [{"rule": "affiliate.profile_link", "text": m.group(0)}]
    return []


def _owned_brand(text: str, owned_brands: list[str]) -> list[dict]:
    lowered = text.lower()
    for name in owned_brands:
        if name and name.lower() in lowered:
            return [{"rule": "own_brand", "text": name}]
    return []


def classify(caption: str | None, owned_brands: list[str] | None = None) -> dict:
    """캡션 하나를 판정한다.

    owned_brands 는 이 게시물을 올린 계정이 가진 브랜드를 캡션에서 찾을 때 쓰는
    표기 목록이다 (data/influencer_accounts.json 의 owned_brands 의 aliases).
    본인 브랜드는 캡션에 광고 표기가 없어서 계정 정보 없이는 알 수 없다.
    브랜드 이름이 사람 이름과 같으면(원정요) 그 이름은 넣지 않는다.
    "Make up by 원정요" 같은 작업 크레딧이 본인 브랜드 홍보로 잡힌다.

    반환값:
        verdict: "ad" | "organic" | "unsure"
        is_ad:   True | False | None (unsure)
        hits:    걸린 근거 [{"rule": "disclosure.hashtag", "text": "#광고"}, ...]
        version: 규칙 버전. 규칙을 고치면 올린다
    """
    text = caption or ""
    body, legend = split_legend(text)

    hits: list[dict] = []
    if legend:
        sponsored_icons = [i for i, kind in legend.items() if kind == "sponsored" and i in body]
        if sponsored_icons:
            hits.append({"rule": "legend.sponsored", "text": "".join(sponsored_icons)})
        else:
            hits.append({"rule": "legend.purchase_only", "text": "".join(legend)})

    hits += _find("disclosure", body)
    hits += _find("gifted", body)
    hits += _owned_brand(body, owned_brands or [])
    hits += _find("affiliate", body)
    hits += _profile_link(body)
    hits += _find("negation", body)
    hits += _find("commercial", body)

    groups = {h["rule"].split(".")[0] for h in hits}
    rules = {h["rule"] for h in hits}

    if "legend.sponsored" in rules or groups & {"disclosure", "gifted", "own_brand", "affiliate"}:
        verdict = AD
    elif "negation" in groups or "legend.purchase_only" in rules:
        verdict = ORGANIC
    elif "commercial" in groups:
        verdict = UNSURE
    else:
        verdict = ORGANIC

    return {
        "verdict": verdict,
        "is_ad": {AD: True, ORGANIC: False, UNSURE: None}[verdict],
        "hits": hits,
        "version": RULE_VERSION,
    }
