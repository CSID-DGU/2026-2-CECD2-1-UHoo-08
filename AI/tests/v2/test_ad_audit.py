"""광고 판별 정기 표본 검수의 뽑기·채점. DB 와 LLM 없이 돈다."""
from collections import Counter

from eval.run_ad_audit import dump_line, next_ids, score_records, stratified_sample


def _post(i: int, stage: str, username: str) -> dict:
    return {"id": i, "stage": stage, "username": username}


def test_1차와_2차를_정해진_수만큼_따로_뽑는다():
    posts = [_post(i, "RULE", f"u{i % 3}") for i in range(40)] + [_post(100 + i, "LLM", f"u{i % 3}") for i in range(8)]
    picked = stratified_sample(posts, n_rule=10, n_llm=5, seed=1)

    assert Counter(p["stage"] for p in picked) == {"RULE": 10, "LLM": 5}
    assert len({p["id"] for p in picked}) == 15


def test_한_계정에_몰리지_않게_돌아가며_뽑는다():
    posts = [_post(i, "LLM", "big") for i in range(20)] + [_post(100, "LLM", "a"), _post(101, "LLM", "b")]
    picked = stratified_sample(posts, n_rule=0, n_llm=3, seed=1)

    assert Counter(p["username"] for p in picked) == {"big": 1, "a": 1, "b": 1}


def test_모자라면_있는_만큼만_뽑는다():
    picked = stratified_sample([_post(1, "LLM", "a")], n_rule=5, n_llm=5, seed=1)
    assert [p["id"] for p in picked] == [1]


def test_같은_시드면_같은_표본이다():
    posts = [_post(i, "RULE", f"u{i % 4}") for i in range(30)]
    assert stratified_sample(posts, 7, 0, seed=3) == stratified_sample(posts, 7, 0, seed=3)


def test_골든셋_id_를_이어서_붙인다():
    assert next_ids(["trend-g-0001", "trend-g-0100", "router-g-0500"], 2) == ["trend-g-0101", "trend-g-0102"]
    assert next_ids([], 1) == ["trend-g-0001"]


def _rec(stage: str, predicted, truth, population=None, sampled_at="2026-11-16") -> dict:
    return {"expected": {"is_ad": truth},
            "audit": {"stage": stage, "sampled_at": sampled_at,
                      "population": population or {"RULE": 90, "LLM": 10},
                      "prediction": {"is_ad": predicted}}}


def test_단계별_정확도와_비율로_가중한_전체_정확도():
    records = [_rec("RULE", True, True), _rec("RULE", False, False),
               _rec("LLM", True, True), _rec("LLM", True, False)]
    result = score_records(records)

    assert result["stages"]["RULE"]["accuracy"] == 1.0
    assert result["stages"]["LLM"]["accuracy"] == 0.5
    assert result["weighted"] == 0.9 * 1.0 + 0.1 * 0.5
    assert len(result["wrong"]) == 1


def test_판정하지_못한_것은_정답으로_세지_않는다():
    result = score_records([_rec("LLM", None, True)])
    assert result["stages"]["LLM"]["accuracy"] == 0.0
    assert result["stages"]["LLM"]["unjudged"] == 1


def test_여러_회차의_비율은_회차마다_한_번씩_더한다():
    records = [_rec("RULE", True, True, {"RULE": 80, "LLM": 20}, "2026-11-02"),
               _rec("RULE", True, True, {"RULE": 80, "LLM": 20}, "2026-11-02"),
               _rec("LLM", True, True, {"RULE": 60, "LLM": 40}, "2026-11-16")]
    shares = score_records(records)["stages"]
    assert shares["RULE"]["share"] == 140 / 200


def test_줄_구분_문자는_이스케이프해_한_줄로_쓴다():
    line = dump_line({"caption": "가 나"})
    assert " " not in line and line.splitlines() == [line]
