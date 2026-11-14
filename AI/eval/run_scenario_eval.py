"""시나리오 골든셋으로 추천 경로를 실제로 돌려 성질을 판정한다.

    python -m eval.run_scenario_eval                       test split 으로 잰다
    python -m eval.run_scenario_eval --split dev           규칙, 프롬프트를 고칠 때
    python -m eval.run_scenario_eval --only scenario-g-0007
    python -m eval.run_scenario_eval --limit 5 --out -     리포트를 화면에만 낸다

페르소나는 먼저 DB 에 넣어 둔다(python -m eval.load_synthetic). 실제 키와 실제 DB 를
쓰므로 CI 에서는 돌지 않는다.

레코드마다 이렇게 돈다.
    1. 페르소나의 합성 사용자 id 로 사용자 맥락(프로필, 선호 가중치)을 읽는다
    2. 골든셋에 적힌 질의 해석(query_spec)으로 그 시나리오의 경로를 돈다.
       질의 해석 단계(Normalize, Router)는 거치지 않는다. 라우터는 따로 잰다
    3. 결과를 기대 성질에 대어 본다(eval/scenario_checks.py)

job 을 DB 에 쓰지 않는다. 진행률, 완료 기록 콜백을 넘기지 않으므로 노드는 읽기만 한다.

수치는 test 로 낸다. 규칙과 프롬프트는 dev 를 보고만 고친다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable

from eval.scenario_checks import judge

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "scenario"
REPORT_DIR = Path(__file__).resolve().parent / "reports"

# 리포트에 싣는 실패 사례 수의 하한. README 의 리포트 양식이 5개 이상이다.
실패_사례_최소 = 5

# 시나리오 → 질의 해석에 요청 유형이 없을 때 채울 값
_요청_유형 = {"S1_EVALUATE": "EVALUATE", "S2_SEARCH": "SEARCH", "S6_BUNDLE": "BUNDLE",
              "S7_REFINE": "REFINE"}

# (결과 dict, 상품 정보) 를 돌려준다
OneRun = Callable[[dict], Awaitable[tuple[dict, dict]]]


def read_golden(split: str | None = None, only: str | None = None) -> tuple[list[dict], list[str]]:
    """(레코드, 읽은 파일 이름)."""
    기록: list[dict] = []
    파일들: list[str] = []
    for path in sorted(GOLDEN_DIR.glob("*.jsonl")):
        파일들.append(path.name)
        for 줄 in path.read_text(encoding="utf-8").splitlines():
            if not 줄.strip():
                continue
            rec = json.loads(줄)
            if split is not None and rec.get("split") != split:
                continue
            if only is not None and rec.get("id") != only:
                continue
            기록.append(rec)
    return 기록, 파일들


def initial_state(rec: dict, user_id: str) -> dict:
    """골든셋 레코드 하나를 경로의 처음 상태로 바꾼다.

    추천 기준은 basis 가 있으면 그것, 없으면 질의 해석의 target 이다. 실제 실행에서
    화면의 탭이 문장보다 우선하는 것과 같게, 정한 기준을 질의 해석에도 맞춰 둔다.
    상품 평가는 기준 상품 id 를 질의 해석의 base_product_ref 자리에도 둔다.
    """
    입력 = rec["input"]
    시나리오 = 입력["scenario"]
    스펙 = dict(입력.get("query_spec") or {})
    스펙.setdefault("request_type", _요청_유형.get(시나리오, "SEARCH"))
    기준 = 입력.get("basis") or 스펙.get("target") or "SELF"
    스펙["target"] = 기준
    if 입력.get("base_product_id"):
        스펙.setdefault("base_product_ref", 입력["base_product_id"])

    상태: dict[str, Any] = {
        "job_id": f"eval-{rec['id']}",
        "user_id": user_id,
        "scenario": 시나리오,
        "raw_query": 입력.get("raw_query") or "",
        "query_spec": 스펙,
        "basis": 기준,
        "target_profile": 입력.get("target_profile"),
        "trace": [],
    }
    if 입력.get("base_product_id"):
        상태["base_product_id"] = 입력["base_product_id"]
    return 상태


async def _한_건_실제(rec: dict) -> tuple[dict, dict]:
    from eval.load_synthetic import synthetic_user_id
    from graph.builder import run_scenario
    from services import user_context

    상태 = initial_state(rec, synthetic_user_id(rec["input"]["persona_id"]))
    상태.update(await user_context.load(상태["user_id"], 상태["basis"], 상태["target_profile"]))
    결과 = await run_scenario(상태["scenario"], 상태)
    return 결과.get("result") or {}, 결과.get("product_meta") or {}


async def evaluate(기록: list[dict], 한_건: OneRun) -> dict[str, Any]:
    """성질별, 시나리오별 통과 수와 실패 사례를 모은다. 한 건이 터져도 나머지는 잰다."""
    성질_통과: dict[str, int] = defaultdict(int)
    성질_전체: dict[str, int] = defaultdict(int)
    경로_통과: dict[str, int] = defaultdict(int)
    경로_전체: dict[str, int] = defaultdict(int)
    실패: list[dict] = []

    for rec in 기록:
        시나리오 = rec["input"]["scenario"]
        경로_전체[시나리오] += 1
        try:
            결과, 메타 = await 한_건(rec)
        except Exception as e:
            실패.append({"id": rec["id"], "scenario": 시나리오, "tags": rec.get("tags") or [],
                         "error": repr(e)})
            continue

        판정 = judge(rec["expected"], 결과, 메타)
        for 키, (통과, _) in 판정.items():
            성질_전체[키] += 1
            성질_통과[키] += int(통과)
        틀린 = {키: 설명 for 키, (통과, 설명) in 판정.items() if not 통과}
        if 틀린:
            실패.append({"id": rec["id"], "scenario": 시나리오, "tags": rec.get("tags") or [],
                         "query": rec["input"].get("raw_query"), "틀린_성질": 틀린})
        else:
            경로_통과[시나리오] += 1

    return {
        "총건수": len(기록),
        "성질": {키: (성질_통과[키], 성질_전체[키]) for 키 in 성질_전체},
        "경로": {키: (경로_통과[키], 경로_전체[키]) for 키 in 경로_전체},
        "실패": 실패,
    }


def _비율(통과: int, 전체: int) -> str:
    return f"{통과 / 전체 * 100:.1f}%" if 전체 else "-"


def to_markdown(결과: dict, split: str, 파일들: list[str]) -> str:
    """README 의 리포트 양식(데이터, 핵심 지표, 실패 사례, 다음 조치)으로 쓴다."""
    줄 = [
        f"# 시나리오 골든셋 평가 ({date.today()})",
        "",
        "## 1. 데이터",
        "",
        f"- split: `{split}`, 레코드 {결과['총건수']}건",
        f"- 파일: {', '.join(f'`{f}`' for f in 파일들) or '없음'}",
        "",
        "## 2. 핵심 지표",
        "",
        "| 시나리오 | 모든 성질 통과 / 전체 | 통과율 |",
        "| --- | ---: | ---: |",
    ]
    for 키, (통과, 전체) in sorted(결과["경로"].items()):
        줄.append(f"| `{키}` | {통과} / {전체} | {_비율(통과, 전체)} |")
    줄 += ["", "| 성질 | 통과 / 전체 | 통과율 |", "| --- | ---: | ---: |"]
    for 키, (통과, 전체) in sorted(결과["성질"].items()):
        줄.append(f"| `{키}` | {통과} / {전체} | {_비율(통과, 전체)} |")

    실패 = 결과["실패"]
    줄 += ["", f"## 3. 실패 사례 ({len(실패)}건)", ""]
    if not 실패:
        줄.append("없다.")
    elif len(실패) < 실패_사례_최소:
        줄.append(f"(실패가 {실패_사례_최소}건보다 적다. 있는 것을 모두 싣는다)")
        줄.append("")
    for 사례 in 실패:
        태그 = f" `{' '.join(사례['tags'])}`" if 사례.get("tags") else ""
        질의 = f" {사례['query']}" if 사례.get("query") else ""
        줄.append(f"- **{사례['id']}** `{사례['scenario']}`{태그}{질의}")
        if "error" in 사례:
            줄.append(f"  - 실행 중 오류: {사례['error']}")
            continue
        for 키, 설명 in 사례["틀린_성질"].items():
            줄.append(f"  - `{키}`: {설명}")
    if 실패:
        줄 += ["", "원인 추정:", "", "- (여기에 적는다)"]

    줄 += ["", "## 4. 다음 조치", "", "- (여기에 적는다)"]
    return "\n".join(줄)


def main() -> None:
    ap = argparse.ArgumentParser(description="시나리오 골든셋 평가")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--only", help="이 id 하나만 돌린다")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 돌린다")
    ap.add_argument("--out", help="리포트 경로. '-' 면 화면에만 낸다. "
                                  "기본은 eval/reports/scenario_<오늘>.md")
    args = ap.parse_args()

    split = None if args.split == "all" else args.split
    기록, 파일들 = read_golden(split, args.only)
    if args.limit:
        기록 = 기록[:args.limit]
    if not 기록:
        print(f"돌릴 레코드가 없다: {GOLDEN_DIR} (split={args.split}, only={args.only})")
        return

    본문 = to_markdown(asyncio.run(evaluate(기록, _한_건_실제)), args.split, 파일들)
    if args.out == "-":
        print(본문)
        return
    경로 = Path(args.out) if args.out else REPORT_DIR / f"scenario_{date.today():%Y%m%d}.md"
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(본문 + "\n", encoding="utf-8")
    print(f"저장: {경로}")


if __name__ == "__main__":
    main()
