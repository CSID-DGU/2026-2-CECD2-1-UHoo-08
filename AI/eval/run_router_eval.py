"""골든셋으로 Normalize·Router 정확도를 잰다.

프롬프트를 고쳤을 때 나아졌는지 나빠졌는지를 눈이 아니라 수치로 본다.
모델을 바꿔 가며 견주는 것도 같은 러너로 한다.

    python -m eval.run_router_eval                      test split 으로 잰다
    python -m eval.run_router_eval --split dev          프롬프트를 고칠 때
    python -m eval.run_router_eval --out eval/reports/router_20260929.md
    python -m eval.run_router_eval --version v1         예전 문제로 잰다

조건을 고르면 시나리오 결정 실험으로 돈다. 같은 문제를 여러 번 반복해 평균과
흩어진 정도를 내고, 되묻기 판단, 확률의 오차, 시간, 비용까지 잰다.

    python -m eval.run_router_eval --condition a2 --runs 3
    python -m eval.run_router_eval --condition a3 --split dev --fit-target 0.97
    python -m eval.run_router_eval --condition a3 --threshold 0.6,0.8 --out eval/reports/experiments/a_router/a3_20261119.md
    python -m eval.run_router_eval --condition a3 --dump a3.json        실행 결과를 남긴다
    python -m eval.run_router_eval --condition a3 --load a3.json --threshold 0.8   다시 채점만 한다

수치는 test 로 낸다. 프롬프트는 dev 를 보고만 고친다. 골든셋에 맞춰 튜닝한
결과를 성능이라고 부르지 않기 위해서다.

기대값에 적힌 키만 본다. 모든 필드를 고정하면 프롬프트를 조금 고쳐도
골든셋이 통째로 깨져서, 나아졌는지가 아니라 "또 깨졌다"만 남는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
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


def read_golden(split: str | None = None, version: str | None = None) -> list[dict]:
    """골든셋을 읽는다. version 을 주면 그 버전 파일(`*_v2.jsonl`)만 읽는다."""
    무늬 = f"*_{version}.jsonl" if version else "*.jsonl"
    기록: list[dict] = []
    for path in sorted(GOLDEN_DIR.glob(무늬)):
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
    한_건: Callable[[dict], Awaitable[tuple[dict, str, bool]]],
) -> dict[str, Any]:
    """골든셋을 태우고 항목별 일치율과 틀린 사례를 모은다."""
    맞음: dict[str, int] = defaultdict(int)
    전체: dict[str, int] = defaultdict(int)
    틀림: list[dict] = []

    for rec in 기록:
        입력 = rec["input"]
        질의 = 입력["raw_query"]
        try:
            spec, 경로, 되물음 = await 한_건(입력)
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


async def _한_건_실제(입력: dict) -> tuple[dict, str, bool]:
    """골든셋 한 줄을 실제 관문에 태운다.

    raw_query 만 넘기면 조건 수정을 잴 수 없다. 라우터는 직전 job 이 없으면
    수정할 대상이 없다고 보고 새 검색으로 내리기 때문이다. 그래서 입력에
    적힌 값을 그대로 상태로 넣는다.
    """
    from graph.nodes.normalize import normalize
    from graph.nodes.router import router

    상태: dict = dict(입력)
    상태.update(await normalize(상태))
    상태.update(await router(상태))
    return 상태["query_spec"], 상태["scenario"], bool(상태.get("clarify_question"))


async def run_condition(
    기록: list[dict],
    조건: Callable[[dict], Awaitable[Any]],
    runs: int = 1,
    concurrency: int = 1,
) -> list[list]:
    """조건 하나로 골든셋을 runs 번 태운다. 실행마다 Trial 목록 하나를 돌려준다.

    문제마다 걸린 시간과 그 사이의 LLM 호출 기록을 함께 남긴다. 한 문제가 터져도
    나머지는 잰다. 동시에 여러 문제를 보내면 빨리 끝나지만 걸린 시간이 실제보다
    길게 나올 수 있어, 시간을 재는 실행은 concurrency 를 1 로 둔다.
    """
    from eval.router_metrics import Trial
    from services.llm.usage import collect_calls

    문 = asyncio.Semaphore(max(1, concurrency))

    async def 한_문제(rec: dict):
        async with 문:
            with collect_calls() as 호출:
                시작 = time.perf_counter()
                try:
                    나온 = await 조건(rec["input"])
                except Exception as e:
                    return Trial(rec=rec, outcome=None, seconds=time.perf_counter() - 시작,
                                 calls=list(호출), error=repr(e))
                return Trial(rec=rec, outcome=나온, seconds=time.perf_counter() - 시작,
                             calls=list(호출))

    return [list(await asyncio.gather(*(한_문제(rec) for rec in 기록))) for _ in range(runs)]


def _코드_버전() -> str:
    """리포트에 적을 커밋. 프롬프트 버전을 따로 매기지 않으므로 커밋으로 가리킨다."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, cwd=Path(__file__).parent,
        ).stdout.strip()
    except Exception:
        return "알 수 없음"


def _실행_결과_읽기(경로: Path, 기록: list[dict]) -> tuple[list, str]:
    """저장해 둔 실행 결과와, 그 결과를 낸 커밋.

    커밋을 함께 적기 전의 파일은 실행 결과 목록만 있으므로 커밋을 알 수 없다.
    """
    from eval.router_metrics import from_records

    적힌 = json.loads(경로.read_text(encoding="utf-8"))
    if isinstance(적힌, list):
        return from_records(적힌, 기록), "알 수 없음 (커밋을 적기 전에 저장한 파일)"
    return from_records(적힌["runs"], 기록), 적힌.get("코드") or "알 수 없음"


def _기준값_목록(글: str | None) -> list[float] | None:
    return [float(x) for x in 글.split(",")] if 글 else None


def _실험(args, 기록: list[dict]) -> None:
    from eval.router_conditions import CONDITIONS
    from eval.router_metrics import (
        Thresholds,
        fit_threshold,
        fit_vague_threshold,
        to_markdown,
        to_records,
    )

    조건 = CONDITIONS[args.condition]
    지금_코드 = _코드_버전()
    if args.load:
        # 이미 실행해 둔 결과를 읽는다. 기준값만 바꿔 다시 채점할 때 LLM 을 또 부르지 않는다
        runs, 실행_코드 = _실행_결과_읽기(Path(args.load), 기록)
    else:
        runs = asyncio.run(run_condition(기록, 조건.run, args.runs, args.concurrency))
        실행_코드 = 지금_코드
    if args.dump:
        Path(args.dump).write_text(
            json.dumps({"코드": 실행_코드, "runs": to_records(runs)}, ensure_ascii=False),
            encoding="utf-8")
        print(f"실행 결과 저장: {args.dump}")
    모든_실행 = [t for run in runs for t in run]
    모델 = sorted({c.model for t in 모든_실행 for c in t.calls})

    맞춘_기준 = None
    if args.fit_target is not None:
        맞춘_기준 = fit_threshold(모든_실행, args.fit_target)
        print(f"목표 {args.fit_target:.0%} 를 채우는 가장 낮은 기준값: {맞춘_기준}")

    기준들 = _기준값_목록(args.threshold)
    if 기준들 is None:
        기준들 = [맞춘_기준 if 맞춘_기준 is not None else 조건.thresholds.scenario]
    막연_기준 = args.vague_threshold if args.vague_threshold is not None else 조건.thresholds.vague
    맞춘_막연_기준 = None
    if args.fit_target is not None and args.vague_threshold is None:
        맞춘_막연_기준 = fit_vague_threshold(모든_실행, 기준들[0])
        if 맞춘_막연_기준 is not None:
            막연_기준 = 맞춘_막연_기준
            print(f"되묻기 판단이 가장 잘 맞는 막연함 확률 기준값: {맞춘_막연_기준}")

    for 기준 in 기준들:
        머리말 = {
            "조건": 조건.name,
            "날짜": str(date.today()),
            "문제": f"{args.version or '전체'} `{args.split}` {len(기록)}건",
            "모델": ", ".join(모델) or "LLM 을 부르지 않음",
            # 결과를 낸 프롬프트와 코드는 실행한 때의 커밋이다
            "코드": 실행_코드,
        }
        if args.load:
            머리말["다시 채점한 코드"] = 지금_코드
        if 맞춘_기준 is not None:
            머리말["이 문제에서 맞춘 기준값"] = f"{맞춘_기준} (목표 {args.fit_target:.0%})"
        if 맞춘_막연_기준 is not None:
            머리말["이 문제에서 맞춘 막연함 확률 기준값"] = str(맞춘_막연_기준)
        본문 = to_markdown(runs=runs, thr=Thresholds(scenario=기준, vague=막연_기준), 머리말=머리말)
        if not args.out:
            print(본문)
            continue
        경로 = Path(args.out)
        if len(기준들) > 1:
            경로 = 경로.with_name(f"{경로.stem}_t{기준}{경로.suffix}")
        경로.write_text(본문 + "\n", encoding="utf-8")
        print(f"저장: {경로}")


def main() -> None:
    ap = argparse.ArgumentParser(description="라우터 골든셋 평가")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--version", default="v2", help="문제 버전. all 이면 모든 파일")
    ap.add_argument("--out", help="리포트를 파일로 저장")
    ap.add_argument("--condition", help="실험 조건. 주면 시나리오 결정 실험으로 돈다")
    ap.add_argument("--runs", type=int, default=3, help="반복 횟수 (실험)")
    ap.add_argument("--concurrency", type=int, default=1, help="동시에 보낼 문제 수 (실험)")
    ap.add_argument("--threshold", help="시나리오 확률 기준값. 쉼표로 여럿 주면 기준값마다 리포트를 낸다")
    ap.add_argument("--vague-threshold", type=float, help="막연함 확률 기준값")
    ap.add_argument("--dump", help="실행 결과를 JSON 으로 저장 (실험)")
    ap.add_argument("--load", help="저장해 둔 실행 결과를 읽어 다시 채점한다. LLM 을 부르지 않는다 (실험)")
    ap.add_argument("--fit-target", type=float,
                    help="처리한 질문의 시나리오 일치율 목표. 이를 채우는 가장 낮은 기준값을 찾는다. dev 에서만 쓴다")
    args = ap.parse_args()

    split = None if args.split == "all" else args.split
    version = None if args.version == "all" else args.version
    args.version = version
    기록 = read_golden(split, version)
    if not 기록:
        print(f"골든셋이 없다: {GOLDEN_DIR} (split={args.split}, version={args.version})")
        return

    if args.condition:
        if args.fit_target is not None and args.split != "dev":
            ap.error("--fit-target 은 연습용(dev)에서만 쓴다. 시험용으로 기준값을 정하면 안 된다")
        _실험(args, 기록)
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
