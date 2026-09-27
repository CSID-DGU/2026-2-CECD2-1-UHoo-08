"""데이터 검증이 실제로 어긋남을 잡는지 본다.

잡지 못하는 검증은 있으나 마나다. 통과하는 경우 하나와, 흔히 낼 실수마다
하나씩 본다.
"""
import json

import pytest

from eval import validate


def _쓰기(경로, 레코드들):
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in 레코드들) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def 가짜루트(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "AI_ROOT", tmp_path)
    return tmp_path


def _수집(tmp_path):
    return validate.collect((tmp_path / "data" / "synthetic", tmp_path / "eval" / "golden"))


def test_제대로_된_데이터는_통과한다(가짜루트):
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [{
        "id": "persona-0001", "split": "dev", "source": "claude",
        "skin_type": "DRY",
        "inventory": [{"product_id": "p-1", "usage_type": "USING"}],
    }])
    문제, 상품 = _수집(가짜루트)
    assert 문제 == []
    assert 상품 == {"p-1"}  # 보유 제품의 id 는 그대로 모은다


def test_폴더와_다른_접두어를_잡는다(가짜루트):
    """id 를 복사해 붙이다 보면 다른 폴더의 접두어가 따라온다."""
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl",
         [{"id": "query-0001", "split": "dev", "source": "claude"}])
    문제, _ = _수집(가짜루트)
    assert any("persona-0001 모양이 아니다" in p for p in 문제)


def test_골든셋은_g접미어를_붙인다(가짜루트):
    _쓰기(가짜루트 / "eval/golden/router/router_v1.jsonl", [{
        "id": "router-0001", "split": "test", "source": "claude",
        "input": {}, "expected": {}, "check": "exact",
    }])
    문제, _ = _수집(가짜루트)
    assert any("router-g-0001" in p for p in 문제)


def test_같은_id가_두_번이면_잡는다(가짜루트):
    """파일을 v2 로 복사하면서 id 를 그대로 두는 일이 자주 생긴다.
    겹친 채로 리포트를 만들면 한쪽 결과가 조용히 덮인다."""
    레코드 = {"id": "persona-0001", "split": "dev", "source": "claude"}
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [레코드])
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v2.jsonl", [레코드])
    문제, _ = _수집(가짜루트)
    assert any("id 가 겹친다" in p for p in 문제)


@pytest.mark.parametrize("고친_곳, 값, 조각", [
    ("split", "train", "dev 또는 test"),
    ("source", "gpt", "claude·manual·real"),
])
def test_정해진_값만_받는다(가짜루트, 고친_곳, 값, 조각):
    레코드 = {"id": "persona-0001", "split": "dev", "source": "claude"}
    레코드[고친_곳] = 값
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [레코드])
    문제, _ = _수집(가짜루트)
    assert any(조각 in p for p in 문제)


def test_골든셋에_필수_키가_없으면_잡는다(가짜루트):
    _쓰기(가짜루트 / "eval/golden/compatibility/pairs_v1.jsonl",
         [{"id": "compatibility-g-0001", "split": "dev", "source": "manual"}])
    문제, _ = _수집(가짜루트)
    assert sum("가 없다" in p for p in 문제) == 3  # input·expected·check


def test_판정_방식이_셋_중_하나여야_한다(가짜루트):
    _쓰기(가짜루트 / "eval/golden/router/router_v1.jsonl", [{
        "id": "router-g-0001", "split": "dev", "source": "claude",
        "input": {}, "expected": {}, "check": "eyeball",
    }])
    문제, _ = _수집(가짜루트)
    assert any("exact·contains·property" in p for p in 문제)


def test_보유_제품에_상품_id가_없으면_잡는다(가짜루트):
    """상품 없는 보유 제품은 적재는 되지만 아무것도 걸러내지 못한다."""
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [{
        "id": "persona-0001", "split": "dev", "source": "claude",
        "inventory": [{"opened_at": "2026-08-01"}],
    }])
    문제, _ = _수집(가짜루트)
    assert any("product_id 가 없다" in p for p in 문제)


def test_알_수_없는_보유_상태를_잡는다(가짜루트):
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [{
        "id": "persona-0001", "split": "dev", "source": "claude",
        "inventory": [{"product_id": "p-1", "usage_type": "OWNED"}],
    }])
    문제, _ = _수집(가짜루트)
    assert any("usage_type" in p for p in 문제)


def test_깨진_줄은_그_줄만_알린다(가짜루트):
    경로 = 가짜루트 / "data/synthetic/queries/queries_v1.jsonl"
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(
        json.dumps({"id": "query-0001", "split": "dev", "source": "claude"}) + "\n"
        + "{깨진 줄\n",
        encoding="utf-8",
    )
    문제, _ = _수집(가짜루트)
    assert len(문제) == 1 and "queries_v1.jsonl:2" in 문제[0]


def test_규칙에_없는_자리에_둔_파일을_알린다(가짜루트):
    _쓰기(가짜루트 / "data/synthetic/misc/x_v1.jsonl", [{"id": "x-0001"}])
    문제, _ = _수집(가짜루트)
    assert any("규칙에 없는 자리" in p for p in 문제)


def test_참조한_상품_id를_모은다(가짜루트):
    """--db 검사가 이 목록을 상품 마스터와 대조한다."""
    uuid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    _쓰기(가짜루트 / "data/synthetic/personas/personas_v1.jsonl", [{
        "id": "persona-0001", "split": "dev", "source": "claude",
        "inventory": [{"product_id": uuid, "usage_type": "USING"}],
    }])
    _, 상품 = _수집(가짜루트)
    assert 상품 == {uuid}


def test_같은_페르소나는_항상_같은_사용자가_된다():
    """데이터를 고쳐 다시 넣어도 같은 사람이 여럿 생기면 안 된다."""
    from eval.load_synthetic import synthetic_user_id

    assert synthetic_user_id("persona-0001") == synthetic_user_id("persona-0001")
    assert synthetic_user_id("persona-0001") != synthetic_user_id("persona-0002")
