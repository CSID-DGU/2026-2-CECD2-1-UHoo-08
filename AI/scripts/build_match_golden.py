"""검수 페이지에서 입력한 정답 → ProductMatcher 골든셋 (eval/golden/trend/product_match_v1.jsonl).

검수 페이지(캡션 · 매칭 결과 검수)는 게시물마다 이런 문서를 남긴다.

    {"none": false, "products": ["에스네이처 딥 아쿠아 스쿠알란 베리어 세럼 50ml", "DB 에 없는 제품명"],
     "verdicts": {"<product_id>": "ok" | "bad"}, "note": "", "updated_at": "..."}

- products 는 사람이 적은 실제 언급 제품이다. 상품 마스터 이름과 똑같으면 product_id 로 바꾸고,
  아니면 미등록 제품(unregistered)으로 남긴다.
- verdicts 의 "ok" 는 v1 이 잡은 매칭이 맞다는 뜻이라 정답에 넣는다. "bad" 는 넣지 않는다.
- none 이 true 면 제품 언급이 없는 게시물이다.

검수한 게시물만 쓴다. 검수하지 않은 게시물은 정답이 아니므로 넣지 않는다.
DB 는 읽기만 한다(캡션 · 상품명). 쓴 뒤 `python -m eval.validate --db` 로 검사한다.

    cd AI
    python -m scripts.build_match_golden --labels <검수 문서 폴더>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "eval" / "golden" / "trend" / "product_match_v1.jsonl"
# 광고 골든셋(ad_v1.jsonl)이 trend-g-0001~0100 을 쓴다. 제품 매칭은 1000 + 게시물 ID 로 겹치지 않게 한다
ID_BASE = 1000


def build_record(post: dict, label: dict, name_to_id: dict[str, str]) -> dict:
    """게시물 하나 + 검수 문서 → 골든셋 한 줄."""
    ids: list[str] = []
    unregistered: list[str] = []
    if not label.get("none"):
        for name in label.get("products") or []:
            name = (name or "").strip()
            if not name:
                continue
            pid = name_to_id.get(name)
            if pid:
                ids.append(pid)
            else:
                unregistered.append(name)
        for pid, v in (label.get("verdicts") or {}).items():
            if v == "ok":
                ids.append(pid)
    ids = list(dict.fromkeys(ids))
    unregistered = list(dict.fromkeys(unregistered))
    pid_num = int(post["id"])
    return {
        "id": f"trend-g-{ID_BASE + pid_num:04d}",
        "split": "test" if pid_num % 2 else "dev",
        "source": "real",
        "tags": ["product_match"] + (["no_mention"] if label.get("none") else []),
        "note": label.get("note") or "",
        "input": {"post_id": pid_num, "username": post.get("username", ""), "caption": post.get("caption") or ""},
        "expected": {"product_ids": ids, "unregistered": unregistered, "none": bool(label.get("none"))},
        "check": "exact",
    }


def load_labels(folder: Path) -> dict[int, dict]:
    """검수 문서 폴더(<게시물 ID>.json) → {게시물 ID: 문서}. 비어 있는 문서는 뺀다."""
    out = {}
    for p in sorted(folder.glob("*.json")):
        if not p.stem.isdigit():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("none") or doc.get("products") or any(v in ("ok", "bad") for v in (doc.get("verdicts") or {}).values()):
            out[int(p.stem)] = doc
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, help="검수 문서 폴더 (게시물 ID.json)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    from scripts.evaluate_product_match_v1 import _load

    products, posts = _load()
    name_to_id = {p["name"]: p["product_id"] for p in products if p.get("name")}
    by_id = {int(p["id"]): p for p in posts}
    labels = load_labels(Path(args.labels))
    missing = sorted(set(labels) - set(by_id))
    recs = [build_record(by_id[i], labels[i], name_to_id) for i in sorted(labels) if i in by_id]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    unreg = sum(len(r["expected"]["unregistered"]) for r in recs)
    print(f"{len(recs)}건 저장 → {out} (미등록 제품 {unreg}개, 제품 없음 {sum(r['expected']['none'] for r in recs)}건)")
    if missing:
        print(f"DB 에 없는 게시물 ID 는 건너뜀: {missing}")


if __name__ == "__main__":
    main()
