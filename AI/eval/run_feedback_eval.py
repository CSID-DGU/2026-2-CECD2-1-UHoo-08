"""피드백이 다음 추천에 반영되는지 잰다.

    python -m eval.run_feedback_eval                 test split 으로 잰다
    python -m eval.run_feedback_eval --split dev
    python -m eval.run_feedback_eval --only scenario-g-0101 --out -

데이터는 두 곳에 있다.
    data/synthetic/feedback/feedback_v1.jsonl       피드백 세션. 누른 이유와 되돌린 것의 순서
    eval/golden/scenario/feedback_v1.jsonl          세션 + 질의 → 기대 성질

레코드마다 이렇게 돈다.
    1. 세션의 피드백을 변경 이력으로 바꾸고, 되돌리지 않은 변경을 기본 가중치에 더한다.
       실제 반영(services/preference_apply.py)과 같은 함수를 쓴다
    2. 같은 질의를 기본 가중치와 바뀐 가중치로 각각 돈다
    3. 두 결과를 기대 성질에 대어 본다(eval/feedback_checks.py)

DB 에 쓰지 않는다. 가중치는 메모리에서 계산해 상태에 넣고, 진행률, 완료 기록 콜백을 넘기지
않는다. 페르소나는 먼저 DB 에 넣어 둔다(python -m eval.load_synthetic). 실제 키와 DB 를
쓰므로 CI 에서는 돌지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable

from eval.feedback_checks import judge
from eval.run_scenario_eval import initial_state

AI_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = AI_ROOT / "data" / "synthetic" / "feedback"
GOLDEN_DIR = AI_ROOT / "eval" / "golden" / "scenario"
REPORT_DIR = AI_ROOT / "eval" / "reports"

# 피드백 골든셋 파일 이름의 앞부분. 시나리오 러너는 이 파일을 읽지 않는다
FEEDBACK_PREFIX = "feedback_"

# (레코드, 바뀐 가중치) → (기본 결과, 바뀐 결과)
OnePair = Callable[[dict, dict], Awaitable[tuple[dict, dict]]]


def _읽기(paths: list[Path]) -> list[dict]:
    기록: list[dict] = []
    for path in paths:
        for 줄 in path.read_text(encoding="utf-8").splitlines():
            if 줄.strip():
                기록.append(json.loads(줄))
    return 기록


def read_sessions() -> dict[str, dict]:
    return {s["id"]: s for s in _읽기(sorted(SESSION_DIR.glob("*.jsonl")))}


def read_golden(split: str | None = None, only: str | None = None) -> tuple[list[dict], list[str]]:
    파일들 = sorted(GOLDEN_DIR.glob(f"{FEEDBACK_PREFIX}*.jsonl"))
    기록 = [
        rec for rec in _읽기(파일들)
        if (split is None or rec.get("split") == split) and (only is None or rec.get("id") == only)
    ]
    return 기록, [p.name for p in 파일들]


def session_changes(session: dict) -> list[dict]:
    """세션의 피드백을 변경 이력으로 바꾼다. 되돌린 변경은 reverted 로 표시한다.

    이벤트 하나는 둘 중 하나다.
        {"reasons": [...]}   별로예요와 고른 이유. 점수 항목으로 옮길 수 없는 이유만 있으면 변경이 없다
        {"revert": n}        n 번째 이벤트가 만든 변경을 되돌린다
    """
    from services.preference_apply import _이유, _이유_변경

    변경들: dict[int, dict] = {}
    for 순번, 이벤트 in enumerate(session.get("events") or []):
        if "revert" in 이벤트:
            if 이벤트["revert"] in 변경들:
                변경들[이벤트["revert"]]["reverted"] = True
            continue
        이유들 = [이유 for 이유 in 이벤트.get("reasons") or [] if 이유 in _이유]
        if not 이유들:
            continue
        변화량, 문장 = _이유_변경(이유들)
        변경들[순번] = {"source": "FEEDBACK", "deltas": 변화량, "sentence": 문장, "reverted": False}
    return list(변경들.values())


def session_weights(session: dict) -> dict[str, float]:
    """되돌리지 않은 변경을 기본 가중치에 더한 값. 실제 반영과 같은 합산을 쓴다."""
    from services.preference_apply import _합산

    가중치, _ = _합산([변경 for 변경 in session_changes(session) if not 변경["reverted"]])
    return 가중치


async def _돌리기(rec: dict, 이름: str, 가중치: dict | None) -> dict:
    from eval.load_synthetic import synthetic_user_id
    from graph.builder import run_scenario
    from services import user_context

    상태 = initial_state({**rec, "id": f"{rec['id']}-{이름}"},
                         synthetic_user_id(rec["input"]["persona_id"]))
    상태.update(await user_context.load(상태["user_id"], 상태["basis"], 상태["target_profile"]))
    # DB 에 쌓인 선호 가중치가 아니라 이 비교의 가중치를 쓴다
    상태["weight_prior"] = 가중치
    return (await run_scenario(상태["scenario"], 상태)).get("result") or {}


async def _한_쌍_실제(rec: dict, 가중치: dict) -> tuple[dict, dict]:
    return await _돌리기(rec, "base", None), await _돌리기(rec, "feedback", 가중치)


async def evaluate(기록: list[dict], 세션들: dict[str, dict], 한_쌍: OnePair) -> dict[str, Any]:
    """성질별 통과 수와 실패 사례를 모은다. 한 건이 터져도 나머지는 잰다."""
    통과: dict[str, int] = defaultdict(int)
    전체: dict[str, int] = defaultdict(int)
    실패: list[dict] = []

    for rec in 기록:
        세션_id = rec["input"].get("session_id")
        try:
            세션 = 세션들[세션_id]
            가중치 = session_weights(세션)
            기본, 바뀐 = await 한_쌍(rec, 가중치)
            판정 = judge(rec["expected"], 기본, 바뀐)
        except Exception as e:
            실패.append({"id": rec["id"], "session": 세션_id, "tags": rec.get("tags") or [],
                         "error": repr(e)})
            continue
        for 키, (맞음, _) in 판정.items():
            전체[키] += 1
            통과[키] += int(맞음)
        틀린 = {키: 설명 for 키, (맞음, 설명) in 판정.items() if not 맞음}
        if 틀린:
            실패.append({"id": rec["id"], "session": 세션_id, "tags": rec.get("tags") or [],
                         "query": rec["input"].get("raw_query"), "틀린_성질": 틀린})

    return {
        "총건수": len(기록),
        "성질": {키: (통과[키], 전체[키]) for 키 in 전체},
        "실패": 실패,
    }


def _비율(통과: int, 전체: int) -> str:
    return f"{통과 / 전체 * 100:.1f}%" if 전체 else "-"


def to_markdown(결과: dict, split: str, 파일들: list[str]) -> str:
    """시나리오 리포트에 붙일 "피드백 반영" 절. 리포트 양식의 네 항목을 따른다."""
    줄 = [
        f"# 피드백 반영 ({date.today()})",
        "",
        "## 1. 데이터",
        "",
        f"- split: `{split}`, 레코드 {결과['총건수']}건",
        f"- 파일: {', '.join(f'`{f}`' for f in 파일들) or '없음'}",
        "",
        "## 2. 핵심 지표",
        "",
        "| 성질 | 통과 / 전체 | 통과율 |",
        "| --- | ---: | ---: |",
    ]
    for 키, (통과, 전체) in sorted(결과["성질"].items()):
        줄.append(f"| `{키}` | {통과} / {전체} | {_비율(통과, 전체)} |")

    실패 = 결과["실패"]
    줄 += ["", f"## 3. 실패 사례 ({len(실패)}건)", ""]
    if not 실패:
        줄.append("없다.")
    for 사례 in 실패:
        태그 = f" `{' '.join(사례['tags'])}`" if 사례.get("tags") else ""
        질의 = f" {사례['query']}" if 사례.get("query") else ""
        줄.append(f"- **{사례['id']}** 세션 `{사례.get('session')}`{태그}{질의}")
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
    ap = argparse.ArgumentParser(description="피드백 반영 평가")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--only", help="이 id 하나만 돌린다")
    ap.add_argument("--out", help="리포트 경로. '-' 면 화면에만 낸다. "
                                  "기본은 eval/reports/feedback_<오늘>.md")
    args = ap.parse_args()

    split = None if args.split == "all" else args.split
    기록, 파일들 = read_golden(split, args.only)
    if not 기록:
        print(f"돌릴 레코드가 없다: {GOLDEN_DIR} (split={args.split}, only={args.only})")
        return

    본문 = to_markdown(asyncio.run(evaluate(기록, read_sessions(), _한_쌍_실제)), args.split, 파일들)
    if args.out == "-":
        print(본문)
        return
    경로 = Path(args.out) if args.out else REPORT_DIR / f"feedback_{date.today():%Y%m%d}.md"
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(본문 + "\n", encoding="utf-8")
    print(f"저장: {경로}")


if __name__ == "__main__":
    main()
