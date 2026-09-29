"""골든셋으로 Normalize·Router 정확도를 잰다.

프롬프트를 고쳤을 때 나아졌는지 나빠졌는지를 눈이 아니라 수치로 본다.
모델을 바꿔 가며 견주는 것도 같은 러너로 한다.

    python -m eval.run_router_eval                      test split 으로 잰다
    python -m eval.run_router_eval --split dev          프롬프트를 고칠 때
    python -m eval.run_router_eval --out eval/reports/router_20260929.md

수치는 test 로 낸다. 프롬프트는 dev 를 보고만 고친다. 골든셋에 맞춰 튜닝한
결과를 성능이라고 부르지 않기 위해서다.

기대값에 적힌 키만 본다. 모든 필드를 고정하면 프롬프트를 조금 고쳐도
골든셋이 통째로 깨져서, 나아졌는지가 아니라 "또 깨졌다"만 남는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "router"

# 기대값에 적을 수 있는 키 → 실제 결과에서 그 값을 꺼내는 법.
# 여기 없는 키를 골든셋에 적으면 조용히 무시되는 대신 오류가 난다.
_꺼내기: dict[str, Callable[[dict, str, bool], Any]] = {
    "scenario": lambda spec, 경로, 되물음: 경로,
    "needs_clarification": lambda spec, 경로, 되물음: 되물음,
    "request_type": lambda spec, *_: spec.get("request_type"),
    "category": lambda spec, *_: spec.get("category"),
    "target": lambda spec, *_: spec.get("target"),
    "use_env": lambda spec, *_: spec.get("use_env"),
    "value_seeking": lambda spec, *_: spec.get("value_seeking"),
    "budget_max": lambda spec, *_: (spec.get("budget") or {}).get("max"),
    "budget_total": lambda spec, *_: (spec.get("budget") or {}).get("total"),
    "base_product_ref_present": lambda spec, *_: bool(spec.get("base_product_ref")),
}


def read_golden(split: str | None = None) -> list[dict]:
    기록: list[dict] = []
    for path in sorted(GOLDEN_DIR.glob("*.jsonl")):
        for 줄 in path.read_text(encoding="utf-8").splitlines():
            if not 줄.strip():
                continue
            rec = json.loads(줄)
            if split is None or rec.get("split") == split:
                기록.append(rec)
    return 기록


def compare(expected: dict, spec: dict, 경로: str, 되물음: bool) -> dict[str, bool]:
    """기대값에 적힌 키만 견준다."""
    결과: dict[str, bool] = {}
    for 키, 기대 in expected.items():
        if 키 not in _꺼내기:
            raise KeyError(f"기대값에 쓸 수 없는 키다: {키}. eval/run_router_eval.py 참고")
        결과[키] = _꺼내기[키](spec, 경로, 되물음) == 기대
    return 결과


async def evaluate(
    기록: list[dict],
    한_건: Callable[[str], Awaitable[tuple[dict, str, bool]]],
) -> dict[str, Any]:
    """골든셋을 태우고 항목별 일치율과 틀린 사례를 모은다."""
    맞음: dict[str, int] = defaultdict(int)
    전체: dict[str, int] = defaultdict(int)
    틀림: list[dict] = []

    for rec in 기록:
        질의 = rec["input"]["raw_query"]
        try:
            spec, 경로, 되물음 = await 한_건(질의)
        except Exception as e:  # 한 건이 터져도 나머지는 잰다
            틀림.append({"id": rec["id"], "query": 질의, "error": repr(e)})
            전체["실행"] += 1
            continue

        판정 = compare(rec["expected"], spec, 경로, 되물음)
        for 키, 맞았나 in 판정.items():
            전체[키] += 1
            맞음[키] += int(맞았나)

        틀린_키 = [키 for 키, 맞았나 in 판정.items() if not 맞았나]
        if 틀린_키:
            틀림.append({
                "id": rec["id"], "query": 질의, "tags": rec.get("tags") or [],
                "틀린_항목": {
                    키: {"기대": rec["expected"][키],
                         "실제": _꺼내기[키](spec, 경로, 되물음)}
                    for 키 in 틀린_키
                },
            })

    return {"총건수": len(기록), "맞음": dict(맞음), "전체": dict(전체), "틀림": 틀림}


def to_markdown(결과: dict, split: str) -> str:
    총 = 결과["총건수"]
    줄 = [
        f"# 라우터 골든셋 평가 ({date.today()})",
        "",
        f"- split: `{split}`",
        f"- 질의 {총}건",
        "",
        "## 항목별 일치율",
        "",
        "| 항목 | 맞음 / 전체 | 일치율 |",
        "| --- | ---: | ---: |",
    ]
    for 키 in sorted(결과["전체"]):
        맞 = 결과["맞음"].get(키, 0)
        전 = 결과["전체"][키]
        줄.append(f"| `{키}` | {맞} / {전} | {맞 / 전 * 100:.1f}% |")

    줄 += ["", f"## 틀린 사례 ({len(결과['틀림'])}건)", ""]
    if not 결과["틀림"]:
        줄.append("없다.")
    for 사례 in 결과["틀림"]:
        태그 = f" `{' '.join(사례.get('tags') or [])}`" if 사례.get("tags") else ""
        줄.append(f"- **{사례['id']}**{태그} — {사례['query']}")
        if "error" in 사례:
            줄.append(f"  - 실행 중 오류: {사례['error']}")
            continue
        for 키, 값 in 사례["틀린_항목"].items():
            줄.append(f"  - `{키}` 기대 `{값['기대']!r}` · 실제 `{값['실제']!r}`")

    줄 += ["", "## 다음 조치", "", "- (여기에 적는다)"]
    return "\n".join(줄)


async def _한_건_실제(질의: str) -> tuple[dict, str, bool]:
    from graph.nodes.normalize import normalize
    from graph.nodes.router import router

    상태: dict = {"raw_query": 질의}
    상태.update(await normalize(상태))
    상태.update(await router(상태))
    return 상태["query_spec"], 상태["scenario"], bool(상태.get("clarify_question"))


def main() -> None:
    ap = argparse.ArgumentParser(description="라우터 골든셋 평가")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--out", help="리포트를 파일로 저장")
    args = ap.parse_args()

    split = None if args.split == "all" else args.split
    기록 = read_golden(split)
    if not 기록:
        print(f"골든셋이 없다: {GOLDEN_DIR} (split={args.split})")
        return

    결과 = asyncio.run(evaluate(기록, _한_건_실제))
    본문 = to_markdown(결과, args.split)

    if args.out:
        Path(args.out).write_text(본문 + "\n", encoding="utf-8")
        print(f"저장: {args.out}")
    else:
        print(본문)


if __name__ == "__main__":
    main()
