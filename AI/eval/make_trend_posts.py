"""Trend v1 검증용 합성 게시물을 만든다 → data/synthetic/trend/posts_v1.jsonl

운영 DB 에 넣지 않는다. 모든 레코드는 source_kind="synthetic" 이고, rules/trend_score 는
allow_synthetic=True 가 아니면 이 데이터를 거부한다.

제품 10개에 언급 게시물을 1·2·3·4·5·6·8·10·12·15개(합 66) 배분하고, 각 제품에 확인하려는
성질을 하나씩 심었다. 같은 시드로 다시 돌리면 같은 파일이 나온다.

    cd AI
    python -m eval.make_trend_posts

| 제품 | 게시물 | 심은 성질 |
| --- | --- | --- |
| syn-p01 | 1  | 작성자 1명 → TOP 10 자격 없음 |
| syn-p02 | 2  | 같은 작성자 2번 → 작성자 1명이라 자격 없음 |
| syn-p03 | 3  | 작성자 3명 · 소형 계정 · 비광고 · 최근 |
| syn-p04 | 4  | 전부 광고 판별 전(is_ad=None) |
| syn-p05 | 5  | 3개가 28일 밖 → 2개만 집계 |
| syn-p06 | 6  | 4개가 좋아요 숨김(결측) |
| syn-p07 | 8  | 대형 계정 위주 · 오래된 글(2~4주 전) |
| syn-p08 | 10 | 작성자 10명 · 비광고 · 최근 → 1위 후보 |
| syn-p09 | 12 | 작성자 다양하나 10개가 광고 |
| syn-p10 | 15 | 본인 브랜드 계정 1명이 12번 + 다른 작성자 3명 → 반복 감쇠 |
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

AS_OF = date(2026, 11, 3)
OUT = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "trend" / "posts_v1.jsonl"

# 작성자: 이름 · 팔로워 · 연령대 · 평소 좋아요 수준
AUTHORS = [
    ("syn_a01", 2_100, "10s", 180), ("syn_a02", 5_400, "10s", 420), ("syn_a03", 8_800, "20s", 610),
    ("syn_a04", 15_000, "20s", 900), ("syn_a05", 32_000, "20s", 1_500), ("syn_a06", 47_000, "30s+", 1_900),
    ("syn_a07", 88_000, "30s+", 3_100), ("syn_a08", 120_000, "20s", 4_200), ("syn_a09", 260_000, "30s+", 7_800),
    ("syn_a10", 580_000, "30s+", 15_000), ("syn_a11", 900, "10s", 70), ("syn_a12", 12_500, "10s", 1_100),
    ("syn_a13", 64_000, "20s", 2_400), ("syn_a14", 150_000, "30s+", 5_000), ("syn_a15", 3_300, "20s", 260),
    ("syn_brand", 41_000, "20s", 1_200),  # syn-p10 을 만드는 브랜드 대표 계정
]
A = {a[0]: a for a in AUTHORS}


def _post(rng, n, product, author, days_ago, *, is_ad=False, hide_likes=False, boost=1.0):
    name, followers, age, base = A[author]
    likes = None if hide_likes else max(0, int(rng.gauss(base * boost, base * 0.25)))
    comments = max(0, int(rng.gauss(base * boost * 0.03, base * 0.01)))
    return {
        "id": f"trend-{n:04d}", "split": "dev", "source": "claude",
        "tags": [product], "note": "",
        "input": {
            "post_id": f"syn-post-{n:04d}", "product_id": product, "author": author,
            "followers": followers, "age_group": age, "like_count": likes, "comment_count": comments,
            "is_ad": is_ad, "posted_at": (AS_OF - timedelta(days=days_ago)).isoformat(),
            "source_kind": "synthetic",
        },
    }


def build() -> list[dict]:
    rng = random.Random(133)
    rows, n = [], 0

    def add(product, author, days_ago, **kw):
        nonlocal n
        n += 1
        rows.append(_post(rng, n, product, author, days_ago, **kw))

    add("syn-p01", "syn_a05", 2)
    add("syn-p02", "syn_a07", 1); add("syn-p02", "syn_a07", 4)
    for a, d in (("syn_a01", 1), ("syn_a11", 2), ("syn_a15", 3)):
        add("syn-p03", a, d)
    for a, d in (("syn_a03", 2), ("syn_a04", 5), ("syn_a12", 6), ("syn_a13", 9)):
        add("syn-p04", a, d, is_ad=None)
    for a, d in (("syn_a02", 3), ("syn_a06", 6), ("syn_a08", 30), ("syn_a09", 35), ("syn_a14", 40)):
        add("syn-p05", a, d)
    for k, (a, d) in enumerate((("syn_a03", 1), ("syn_a04", 2), ("syn_a05", 4), ("syn_a06", 5), ("syn_a12", 8), ("syn_a13", 10))):
        add("syn-p06", a, d, hide_likes=k < 4)
    for a, d in (("syn_a09", 14), ("syn_a10", 16), ("syn_a14", 18), ("syn_a08", 20), ("syn_a09", 22),
                 ("syn_a10", 24), ("syn_a14", 25), ("syn_a07", 27)):
        add("syn-p07", a, d, is_ad=a == "syn_a10")
    for a, d in zip(("syn_a01", "syn_a02", "syn_a03", "syn_a04", "syn_a05", "syn_a06", "syn_a11", "syn_a12", "syn_a13", "syn_a15"),
                    (0, 1, 1, 2, 2, 3, 4, 5, 6, 7)):
        add("syn-p08", a, d, boost=1.6)
    for k, (a, d) in enumerate(zip(("syn_a01", "syn_a02", "syn_a03", "syn_a04", "syn_a05", "syn_a06",
                                    "syn_a07", "syn_a08", "syn_a11", "syn_a12", "syn_a13", "syn_a15"),
                                   (0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7))):
        add("syn-p09", a, d, is_ad=k < 10, boost=1.6)
    for d in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
        add("syn-p10", "syn_brand", d, is_ad=True, boost=1.2)
    for a, d in (("syn_a04", 3), ("syn_a13", 5), ("syn_a02", 8)):
        add("syn-p10", a, d)

    return rows


def main() -> None:
    rows = build()
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{OUT.name}: 합성 게시물 {len(rows)}개")


if __name__ == "__main__":
    main()
