"""ProductMatcher 실패 단계 분류와 지표 (LLM 없음, 같은 입력이면 같은 결과).

정답은 사람이 검수한 골든셋(eval/golden/trend/product_match_v2.jsonl)에서만 온다. 검수하지 않은
게시물은 여기 들어오지 않는다. 매처가 낸 결과를 정답으로 쓰지 않는다.

골든셋 항목 하나 = 게시물에서 실제로 언급된 제품 하나.
  kind  in_db        상품 마스터에 있는 제품 (product_id)
        not_in_db    범위(base · sun · lip · skincare) 안 화장품인데 마스터에 없음
        out_of_scope 범위 밖 화장품 (아이 · 치크 · 클렌징 …)
        not_cosmetic 화장품 아님
        unspecific   제품을 특정할 수 없음 (브랜드만 · 컬러명만 · 세트)
  mentions  이 제품을 가리키는 추출 언급의 번호 (extract-v1 캐시 순서). 비어 있으면 추출이 놓친 것

in_db 항목 하나가 어디서 멈췄는지 (STAGES, 뒤로 갈수록 많이 간 것)
  extract_miss      추출이 그 제품을 뽑지 않음
  extract_misclass  뽑았지만 brand_only · category_only 로 봄
  retrieval_miss    후보 top K 에 정답이 없음
  pool_cut          후보에는 있었지만 판정 LLM 에 보여 준 후보(이름 점수 60 바닥 등)에서 빠짐
  rule_wrong        규칙이 다른 제품으로 확정함
  llm_wrong         판정 LLM 이 다른 제품 · unmatched · review 를 냄
  accept_blocked    판정 LLM 은 정답을 골랐는데 인정 규칙(accept_choice)이 막음
  matched           정답 제품으로 이음
같은 제품을 여러 언급이 가리키면 가장 멀리 간 언급으로 본다.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

STAGES = ["extract_miss", "extract_misclass", "retrieval_miss", "pool_cut", "rule_wrong", "llm_wrong",
          "accept_blocked", "matched"]
KINDS = ["in_db", "not_in_db", "out_of_scope", "not_cosmetic", "unspecific"]
MATCHED = "matched"


@dataclass
class Row:
    """매처가 언급 하나에 낸 결과 중 분류에 필요한 것."""
    mention_type: str
    status: str
    product_id: str | None
    method: str | None              # rule · llm · hashtag · None
    candidates: list[str]           # 검색 순위대로 product_id
    pool: list[str]                 # 판정 LLM 에 보여 준 product_id
    llm_choice: object = None


def classify_item(product_id: str, mention_idx: list[int], rows: list[Row], k: int | None = None) -> str:
    """골든셋 in_db 항목 하나 → STAGES 중 하나."""
    reached = []
    for i in mention_idx:
        if i >= len(rows):
            continue
        r = rows[i]
        cands = r.candidates[:k] if k else r.candidates
        if r.status == MATCHED and r.product_id == product_id:
            reached.append("matched")
        elif r.mention_type != "product":
            reached.append("extract_misclass")
        elif product_id not in cands:
            reached.append("retrieval_miss")
        elif r.method == "rule" and r.status == MATCHED:
            reached.append("rule_wrong")
        elif product_id not in r.pool:
            reached.append("pool_cut")
        elif r.llm_choice == product_id:
            reached.append("accept_blocked")
        else:
            reached.append("llm_wrong")
    if not reached:
        return "extract_miss"
    return max(reached, key=STAGES.index)


def gold_items(gold: dict, master_ids: set[str] | None = None) -> list[dict]:
    """골든셋 한 줄 → 항목 목록. master_ids 를 주면 그 안에 없는 in_db 는 not_in_db 로 본다 (당시 마스터 재현)."""
    out = []
    for it in gold["expected"]["items"]:
        it = dict(it)
        if it["kind"] == "in_db" and master_ids is not None and it["product_id"] not in master_ids:
            it["kind"] = "not_in_db"
            it["note"] = "당시 마스터에 없음"
        out.append(it)
    return out


def evaluate(golds: list[dict], rows_by_post: dict[int, list[Row]], ks=(1, 5, 10, 20),
             master_ids: set[str] | None = None) -> dict:
    """검수된 게시물만으로 지표를 낸다.

    candidate_recall@K  추출이 제품으로 뽑은 in_db 항목 중 후보 top K 에 정답이 있는 비율
    auto_precision      규칙으로 확정한 것 중 맞은 비율
    precision           matched 전체(규칙 + LLM + 해시태그) 중 맞은 비율
    recall_in_db        in_db 항목 중 정답으로 이은 비율
    match_rate_all      범위 안 · 밖 특정 가능한 화장품 항목(in_db + not_in_db + out_of_scope) 중 정답으로 이은 비율
    """
    stages = Counter()
    kinds = Counter()
    recall_k = {k: [0, 0] for k in ks}
    pred = {"rule": [0, 0], "llm": [0, 0], "hashtag": [0, 0]}   # [맞음, 전체]
    wrong = []
    for g in golds:
        pid_post = g["input"]["post_id"]
        rows = rows_by_post.get(pid_post, [])
        items = gold_items(g, master_ids)
        gold_ids = {it["product_id"] for it in items if it["kind"] == "in_db"}
        for it in items:
            kinds[it["kind"]] += 1
            if it["kind"] != "in_db":
                continue
            stage = classify_item(it["product_id"], it.get("mentions") or [], rows)
            stages[stage] += 1
            extracted = [rows[i] for i in it.get("mentions") or [] if i < len(rows) and rows[i].mention_type == "product"]
            if extracted:
                for k in ks:
                    recall_k[k][1] += 1
                    recall_k[k][0] += any(it["product_id"] in r.candidates[:k] for r in extracted)
        seen = set()
        for i, r in enumerate(rows):
            if r.status != MATCHED or not r.product_id or (r.product_id, r.method) in seen:
                continue
            seen.add((r.product_id, r.method))
            m = r.method if r.method in pred else "llm"
            ok = r.product_id in gold_ids
            pred[m][1] += 1
            pred[m][0] += ok
            if not ok:
                wrong.append({"post_id": pid_post, "mention": i, "product_id": r.product_id, "method": r.method})
    n_in = kinds["in_db"]
    n_all = kinds["in_db"] + kinds["not_in_db"] + kinds["out_of_scope"]
    tp = sum(v[0] for v in pred.values())
    npred = sum(v[1] for v in pred.values())
    return {
        "posts": len(golds),
        "items": dict(kinds),
        "stages": {s: stages[s] for s in STAGES},
        "candidate_recall": {f"@{k}": _ratio(*recall_k[k]) for k in ks},
        "auto_precision": _ratio(*pred["rule"]),
        "precision": _ratio(tp, npred),
        "precision_by_method": {m: _ratio(*v) for m, v in pred.items()},
        "recall_in_db": _ratio(stages["matched"], n_in),
        "match_rate_all": _ratio(stages["matched"], n_all),
        "false_positives": wrong,
    }


def _ratio(a: int, b: int) -> dict:
    return {"hit": a, "total": b, "rate": round(a / b, 4) if b else None}
