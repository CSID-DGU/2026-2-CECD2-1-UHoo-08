"""캡션 → 제품 언급 추출 (ProductMatcher v1 1단계).

LLM(LLMRole.MATCH)이 캡션에서 언급된 제품을 구조화해 뽑는다. 응답은 믿지 않고 검사한다.

- 스키마(MentionOut)에 맞지 않는 항목은 버린다. 응답 전체가 틀이 깨졌으면 다시 묻는다.
- evidence 가 캡션에 실제로 없는 항목은 버린다. 원문에 없는 제품을 지어낸 것이다.
- mention_type 과 product_name 이 어긋나면(브랜드만 언급인데 제품명이 있음 등) 버린다.

결과는 (게시물 ID, 캡션 해시, 프롬프트 버전)으로 캐시한다. 같은 게시물을 같은 프롬프트로
두 번 부르지 않는다. 캡션이 고쳐지거나 프롬프트 버전이 바뀌면 새로 부른다.

LLM 호출 실패(시간 초과 · 네트워크)는 그대로 올린다. 판정 불가로 덮지 않는다.
config · LLM SDK 는 함수 안에서 import 한다.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ValidationError, model_validator

from prompts.product_extract import EXTRACT_SYSTEM, EXTRACT_VERSION, build_extract_user

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "product_extract"
RETRIES = 2
TIMEOUT_S = 60.0


class MentionOut(BaseModel):
    brand: Optional[str] = None
    product_name: Optional[str] = None
    variant: Optional[str] = None
    category: Literal["base", "sun", "lip", "skincare", "other"] | None = None
    evidence: str
    mention_type: Literal["product", "brand_only", "category_only"]
    specificity: Literal["exact", "partial", "ambiguous"]

    @model_validator(mode="after")
    def _consistent(self):
        if self.mention_type == "product" and not (self.product_name or "").strip():
            raise ValueError("product 인데 product_name 이 없다")
        if self.mention_type == "brand_only" and (self.product_name or "").strip():
            raise ValueError("brand_only 인데 product_name 이 있다")
        if self.mention_type == "brand_only" and not (self.brand or "").strip():
            raise ValueError("brand_only 인데 brand 가 없다")
        if not self.evidence.strip():
            raise ValueError("evidence 가 비었다")
        return self


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def evidence_in_caption(evidence: str, caption: str) -> bool:
    """근거가 캡션에 있는지. 공백 · 줄바꿈 · 대소문자 차이만 허용한다."""
    e = _squash(evidence)
    return bool(e) and e in _squash(caption)


def parse_extraction(result: Any, caption: str) -> tuple[list[dict], list[dict]] | None:
    """LLM 응답 → (쓸 수 있는 언급, 버린 항목과 이유). 응답 틀이 깨졌으면 None (다시 묻는다)."""
    if not isinstance(result, dict) or not isinstance(result.get("mentions"), list):
        return None
    kept, dropped, seen = [], [], set()
    for item in result["mentions"]:
        try:
            m = MentionOut.model_validate(item)
        except ValidationError as e:
            dropped.append({"item": item, "why": "스키마: " + e.errors()[0].get("msg", "")})
            continue
        if not evidence_in_caption(m.evidence, caption):
            dropped.append({"item": item, "why": "evidence 가 캡션에 없음"})
            continue
        key = (_squash(m.brand or ""), _squash(m.product_name or ""), m.mention_type)
        if key in seen:
            continue
        seen.add(key)
        kept.append(m.model_dump())
    return kept, dropped


def cache_key(post_id: Any, caption: str, version: str = EXTRACT_VERSION) -> str:
    h = hashlib.sha1((caption or "").encode("utf-8")).hexdigest()[:12]
    return f"{post_id}:{h}:{version}"


class ExtractCache:
    """한 줄에 {key, value} 인 JSONL. 실험 결과를 지우지 않고 쌓는다."""

    def __init__(self, path: Path | None = None):
        self.path = path or CACHE_DIR / f"{EXTRACT_VERSION}.jsonl"
        self.data: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.data[row["key"]] = row["value"]

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, value: dict) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


async def extract_post(post: dict, llm, cache: ExtractCache | None = None,
                       owned_brands: list[str] | None = None) -> dict:
    """게시물 하나 → {mentions, dropped, attempts, cached, failed}.

    post: {id, caption, username}
    failed=True 면 RETRIES 번 다시 물어도 응답 틀이 깨진 것이다 (호출 자체의 실패는 예외로 올린다).
    """
    caption = post.get("caption") or ""
    key = cache_key(post["id"], caption)
    if cache and (hit := cache.get(key)) is not None:
        return {**hit, "cached": True}
    if not caption.strip():
        out = {"mentions": [], "dropped": [], "attempts": 0, "failed": False}
    else:
        user = build_extract_user(caption, post.get("username") or "", owned_brands)
        out = None
        for attempt in range(1, RETRIES + 2):
            result = await llm.chat_json(system=EXTRACT_SYSTEM, user=user, timeout=TIMEOUT_S,
                                         temperature=0.0 if attempt == 1 else 0.3)
            parsed = parse_extraction(result, caption)
            if parsed is not None:
                out = {"mentions": parsed[0], "dropped": parsed[1], "attempts": attempt, "failed": False}
                break
        if out is None:
            out = {"mentions": [], "dropped": [], "attempts": RETRIES + 1, "failed": True}
    if cache and not out["failed"]:
        cache.put(key, out)
    return {**out, "cached": False}
