"""광고 판별 정기 표본 검수.

운영 중에 판정된 게시물을 몇십 건씩 뽑아, 판정을 숨긴 채 사람이 라벨을
붙이고 맞춰 본다. 골든셋 한 번으로 잰 수치는 표본이 작고, 계정이 바뀌면
처음 보는 표기가 생긴다. 2주에 한 번 정도 돌려 쌓으면 수치가 정확해지고
새 표기도 잡힌다.

    python -m eval.run_ad_audit sample --out ad_audit.jsonl     표본을 뽑고 판정을 숨겨 저장
    python -m eval.run_ad_audit label ad_audit.jsonl            터미널에서 라벨링 (이어서 할 수 있다)
    python -m eval.run_ad_audit finalize ad_audit.jsonl         골든셋으로 옮긴다
    python -m eval.run_ad_audit score                           회차별·누적 정확도
    python -m eval.run_ad_audit score --out eval/reports/ad_audit_20261116.md

1차 규칙이 확정한 것과 2차 LLM 으로 넘어간 것을 따로 정해진 수만큼 뽑는다.
그냥 무작위로 뽑으면 2차로 가는 게시물이 열에 하나라 2차 수치를 낼 수 없다.
전체 정확도는 그 기간의 1차·2차 비율로 가중해 계산한다.

검수 회차의 split 은 test 이고, 나중에 dev 로 바꾸지 않는다(eval/README.md 의 split
규칙). 한 회차는 뽑을 때 쓰던 규칙 · 프롬프트 버전(audit.prediction.version)의 성능을
잰 기록이다. 그 회차를 보고 규칙이나 프롬프트를 고쳤으면, 고친 버전의 수치는 다음
회차로 낸다. 고친 버전으로 지난 회차를 다시 채점하지 않는다.

라벨링 중인 파일(finalize 전)은 저장소 밖에 있어 골든셋으로 거를 수 없다. 그 사이에
다시 뽑으면 sample --exclude 로 그 파일을 넘긴다. 넘긴 파일의 게시물은 뽑지 않는다.

config · DB · LLM 은 함수 안에서 import 한다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "trend"
AUDIT_GLOB = "ad_audit_*.jsonl"
STAGES = ("RULE", "LLM")

# str.splitlines 가 줄바꿈으로 보는 문자. 그대로 두면 JSONL 한 줄이 여러 줄로 잘린다
_LINE_BREAKS = {chr(c): "\\u%04x" % c for c in (0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029)}


def dump_line(rec: dict) -> str:
    s = json.dumps(rec, ensure_ascii=False)
    for c, e in _LINE_BREAKS.items():
        s = s.replace(c, e)
    return s


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """같은 폴더의 임시 파일에 다 쓴 뒤 바꿔 끼운다. 쓰다 끊겨도 이전 완전본이 남는다."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(dump_line(r) + "\n" for r in rows))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ── 뽑기 ─────────────────────────────────────────────────────────────

def stratified_sample(posts: list[dict], n_rule: int, n_llm: int, seed: int) -> list[dict]:
    """1차가 확정한 것(stage=RULE)과 2차로 간 것(stage=LLM)을 따로 뽑는다.

    한 계정이 몰리지 않게 계정마다 돌아가며 하나씩 뽑는다.
    """
    rng = random.Random(seed)
    picked = []
    for stage, n in (("RULE", n_rule), ("LLM", n_llm)):
        by_account: dict[str, list[dict]] = defaultdict(list)
        for p in posts:
            if p["stage"] == stage:
                by_account[p["username"]].append(p)
        for rows in by_account.values():
            rng.shuffle(rows)
        accounts = sorted(by_account)
        rng.shuffle(accounts)
        taken = 0
        while taken < n and any(by_account[a] for a in accounts):
            for a in accounts:
                if taken < n and by_account[a]:
                    picked.append(by_account[a].pop())
                    taken += 1
    rng.shuffle(picked)
    return picked


def _seen_post_ids(extra: list[Path] = ()) -> tuple[set[int], set[str]]:
    """골든셋 · 라벨링 중인 검수 파일(extra)에 이미 들어간 게시물. 다시 뽑지 않는다."""
    db_ids: set[int] = set()
    platform_ids: set[str] = set()
    for path in [*GOLDEN_DIR.glob("*.jsonl"), *extra]:
        for rec in read_jsonl(path):
            inp = rec.get("input", {})
            if inp.get("post_id") is not None:
                db_ids.add(inp["post_id"])
            if inp.get("platform_post_id"):
                platform_ids.add(inp["platform_post_id"])
    return db_ids, platform_ids


def build_pool(posts: list[dict], stage_of, seen_db: set[int], seen_platform: set[str]) -> tuple[list[dict], dict]:
    """기간 안 게시물 → (뽑기 후보, 1차 · 2차 비율).

    stage_of(post) 는 "RULE" | "LLM" 을 돌려준다.
    계정 이름이 바뀌면 같은 게시물이 새 account_id 로 다시 저장되고 이전 행이 남는다.
    platform_post_id 가 같은 행은 id 가 가장 작은 하나만 본다.
    비율은 이미 뽑힌 게시물을 빼기 전, 그 기간 전체로 센다. 이전 회차와 기간이 겹칠 때
    빼고 세면 비율이 틀어지고, 그 비율로 가중하는 전체 정확도도 틀어진다.
    """
    unique: dict[str, dict] = {}
    for p in sorted(posts, key=lambda p: p["id"]):
        if (p.get("caption") or "").strip():
            unique.setdefault(p["platform_post_id"], p)
    staged = [{**p, "stage": stage_of(p)} for p in unique.values()]
    population = dict(Counter(p["stage"] for p in staged))
    pool = [p for p in staged if p["id"] not in seen_db and p["platform_post_id"] not in seen_platform]
    return pool, population


async def _sample(days: int, n_rule: int, n_llm: int, seed: int, exclude: list[Path] = ()) -> list[dict]:
    from db.supabase_client import get_supabase
    from rules.ad_disclosure import UNSURE, classify
    from services.ad_classifier import classify_post, owned_brand_aliases
    from services.influencer_collector import ACCOUNTS_PATH

    owned = {a["username"]: a.get("owned_brands", []) for a in json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))}
    sb = get_supabase()
    usernames = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id, username").execute().data}
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    seen_db, seen_platform = _seen_post_ids(exclude)

    posts, start = [], 0
    while True:
        rows = (sb.table("influencer_posts")
                .select("id, account_id, platform_post_id, caption, posted_at")
                .gte("posted_at", since).order("id").range(start, start + 99).execute().data)
        posts += rows
        if len(rows) < 100:
            break
        start += 100

    for p in posts:
        p["username"] = usernames.get(p["account_id"], "")

    def stage_of(p: dict) -> str:
        verdict = classify(p["caption"], owned_brand_aliases(owned.get(p["username"])))["verdict"]
        return "LLM" if verdict == UNSURE else "RULE"

    pool, population = build_pool(posts, stage_of, seen_db, seen_platform)

    picked = stratified_sample(pool, n_rule, n_llm, seed)
    records = []
    for p in picked:
        result = await classify_post(p["caption"], p["username"], owned.get(p["username"]))
        records.append({
            "input": {"post_id": p["id"], "platform_post_id": p["platform_post_id"],
                      "username": p["username"], "posted_at": p["posted_at"], "caption": p["caption"]},
            "expected": {"is_ad": None},
            "audit": {"stage": result["labeled_by"], "population": population,
                      "window_days": days, "sampled_at": date.today().isoformat(),
                      "prediction": {k: result.get(k) for k in ("is_ad", "version", "reason_code", "reason")}},
        })
    return records


# ── 라벨링 ───────────────────────────────────────────────────────────

def label(path: Path) -> None:
    """캡션만 보여 주고 1(광고) / 0(광고 아님)을 받는다. 판정은 보여 주지 않는다."""
    rows = read_jsonl(path)
    todo = [r for r in rows if r["expected"]["is_ad"] is None]
    print(f"{len(rows)}건 중 남은 {len(todo)}건. 1 광고 / 0 광고 아님 / s 건너뛰기 / q 그만 (답할 때마다 저장)")
    for i, rec in enumerate(todo, 1):
        print("\n" + "─" * 60)
        print(f"[{i}/{len(todo)}] @{rec['input']['username']} {rec['input']['posted_at'][:10]}\n")
        print(rec["input"]["caption"])
        while True:
            answer = input("\n광고? [1/0/s/q] ").strip().lower()
            if answer in {"1", "0", "s", "q"}:
                break
        if answer == "q":
            break
        if answer == "s":
            continue
        rec["expected"]["is_ad"] = answer == "1"
        memo = input("메모 (없으면 엔터) ").strip()
        if memo:
            rec["note"] = memo
        write_jsonl(path, rows)
    left = sum(r["expected"]["is_ad"] is None for r in rows)
    print(f"\n저장했다. 남은 {left}건" + ("" if left else ". finalize 로 골든셋에 옮긴다"))


def next_ids(existing_ids: list[str], n: int, prefix: str = "trend-g") -> list[str]:
    nums = [int(m.group(1)) for i in existing_ids if (m := re.fullmatch(rf"{prefix}-(\d+)", i))]
    start = max(nums, default=0) + 1
    return [f"{prefix}-{k:04d}" for k in range(start, start + n)]


def finalize(path: Path) -> Path:
    rows = read_jsonl(path)
    if not rows:
        raise SystemExit(f"{path} 에 검수할 게시물이 없다. 골든셋에 옮기지 않는다")
    left = sum(r["expected"]["is_ad"] is None for r in rows)
    if left:
        raise SystemExit(f"라벨이 안 붙은 {left}건이 있다. label 을 먼저 끝낸다")
    existing = [rec["id"] for p in GOLDEN_DIR.glob("*.jsonl") for rec in read_jsonl(p)]
    sampled_at = rows[0]["audit"]["sampled_at"].replace("-", "")
    out = GOLDEN_DIR / f"ad_audit_{sampled_at}.jsonl"
    if out.exists():
        raise SystemExit(f"{out} 이 이미 있다. 기존 파일은 고치지 않는다")
    golden = [{"id": i, "split": "test", "source": "real", "tags": [r["audit"]["stage"].lower()],
               "note": r.get("note", ""), "input": r["input"], "expected": r["expected"],
               "check": "exact", "audit": r["audit"]}
              for i, r in zip(next_ids(existing, len(rows)), rows)]
    write_jsonl(out, golden)
    return out


# ── 채점 ─────────────────────────────────────────────────────────────

def score_records(records: list[dict]) -> dict[str, Any]:
    """단계별 정확도와, 그 기간 단계 비율로 가중한 전체 정확도."""
    by_stage: dict[str, Counter] = {s: Counter() for s in STAGES}
    population: Counter = Counter()
    wrong = []
    for r in records:
        stage = r["audit"]["stage"]
        predicted, truth = r["audit"]["prediction"]["is_ad"], r["expected"]["is_ad"]
        key = "unjudged" if predicted is None else ("ok" if predicted == truth else "wrong")
        by_stage[stage][key] += 1
        by_stage[stage]["n"] += 1
        if key != "ok":
            wrong.append(r)
    # 회차마다 같은 population 이 모든 줄에 적혀 있다. 회차별로 한 번만 센다
    for sampled_at, pop in {r["audit"]["sampled_at"]: r["audit"]["population"] for r in records}.items():
        population.update(pop)

    def acc(s: str) -> float | None:
        c = by_stage[s]
        return c["ok"] / c["n"] if c["n"] else None

    total = sum(population[s] for s in STAGES)
    weighted = None
    if total and all(acc(s) is not None for s in STAGES if population[s]):
        weighted = sum(population[s] / total * acc(s) for s in STAGES if population[s])
    return {"stages": {s: {**by_stage[s], "accuracy": acc(s), "share": population[s] / total if total else None}
                       for s in STAGES},
            "weighted": weighted, "wrong": wrong}


def _report(files: list[Path], split: str) -> str:
    lines = [f"# 광고 판별 정기 표본 검수 ({date.today().isoformat()})", "", f"- split: `{split}`", ""]
    lines += ["| 회차 | 1차 정확도 | 2차 정확도 | 1차:2차 비율 | 가중 전체 |", "| --- | ---: | ---: | ---: | ---: |"]
    every = []

    def row(name: str, res: dict) -> str:
        cells = []
        for s in STAGES:
            st = res["stages"][s]
            cells.append(f"{st['ok']} / {st['n']} ({st['accuracy']:.1%})" if st["n"] else "-")
        share = res["stages"]["RULE"]["share"]
        ratio = f"{share:.0%} : {1 - share:.0%}" if share is not None else "-"
        weighted = f"{res['weighted']:.1%}" if res["weighted"] is not None else "-"
        return f"| {name} | {cells[0]} | {cells[1]} | {ratio} | {weighted} |"

    for path in files:
        recs = [r for r in read_jsonl(path) if r["split"] == split]
        if recs:
            every += recs
            lines.append(row(path.stem, score_records(recs)))
    if not every:
        return "\n".join(lines + ["", "해당 split 의 검수 기록이 없다."])
    total = score_records(every)
    lines.append(row("**누적**", total))
    lines += ["", f"## 틀리거나 판정하지 못한 사례 ({len(total['wrong'])}건)", ""]
    for r in total["wrong"]:
        pred = r["audit"]["prediction"]
        cap = r["input"]["caption"].replace("\n", " / ")[:120]
        lines.append(f"- **{r['id']}** ({r['audit']['stage']}, {pred.get('reason_code') or pred.get('version')}) "
                     f"정답 `{r['expected']['is_ad']}` · 판정 `{pred['is_ad']}` — {cap}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--out", required=True, help="라벨링할 파일. 저장소 밖에 둔다")
    s.add_argument("--days", type=int, default=14)
    s.add_argument("--rule", type=int, default=15, help="1차가 확정한 것에서 뽑을 수")
    s.add_argument("--llm", type=int, default=15, help="2차로 넘어간 것에서 뽑을 수")
    s.add_argument("--seed", type=int, default=int(date.today().strftime("%Y%m%d")))
    s.add_argument("--exclude", action="append", default=[], help="라벨링 중인 검수 파일. 그 게시물은 뽑지 않는다 (반복 가능)")
    lb = sub.add_parser("label")
    lb.add_argument("path")
    fz = sub.add_parser("finalize")
    fz.add_argument("path")
    sc = sub.add_parser("score")
    sc.add_argument("--split", default="test", choices=["dev", "test"])
    sc.add_argument("--out")
    args = parser.parse_args()

    if args.cmd == "sample":
        out = Path(args.out).expanduser()
        if out.exists():
            # 라벨은 finalize 전까지 이 파일에만 있다. 덮어쓰면 붙인 라벨이 사라진다
            raise SystemExit(f"{out} 이 이미 있다. 다른 경로를 주거나, 라벨링 중이면 label 로 이어서 한다")
        exclude = [Path(p).expanduser() for p in args.exclude]
        missing = [str(p) for p in exclude if not p.exists()]
        if missing:
            raise SystemExit(f"--exclude 파일이 없다: {', '.join(missing)}")
        records = asyncio.run(_sample(args.days, args.rule, args.llm, args.seed, exclude))
        write_jsonl(out, records)
        print(f"{len(records)}건 저장: {args.out}. label 로 라벨링한다")
    elif args.cmd == "label":
        label(Path(args.path))
    elif args.cmd == "finalize":
        print(f"저장: {finalize(Path(args.path))}. python -m eval.validate 로 확인한다")
    elif args.cmd == "score":
        report = _report(sorted(GOLDEN_DIR.glob(AUDIT_GLOB)), args.split)
        if args.out:
            Path(args.out).write_text(report, encoding="utf-8")
        print(report)


if __name__ == "__main__":
    main()
