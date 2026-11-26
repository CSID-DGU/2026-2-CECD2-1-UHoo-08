"""모델 비교 실험의 후보 목록을 본다. 설정도 LLM 도 건드리지 않는다."""
from eval.model_candidates import CANDIDATES, CURRENT
from eval.router_metrics import PRICES_PER_1M


def test_후보마다_가격이_있다():
    """가격이 없으면 비용이 빈칸으로 나와, 비용을 견주는 실험에서 그 모델만 빠진다."""
    assert [이름 for 이름 in CANDIDATES if 이름 not in PRICES_PER_1M] == []


def test_지금_모델이_후보에_있다():
    assert CURRENT in CANDIDATES


def test_후보_이름은_목록의_키와_같다():
    assert all(이름 == 후보.model for 이름, 후보 in CANDIDATES.items())


def test_주소와_키는_둘_다_적거나_둘_다_비운다():
    """하나만 적으면 다른 곳의 키를 엉뚱한 주소로 보내게 된다."""
    for 후보 in CANDIDATES.values():
        assert bool(후보.base_url_from) == bool(후보.api_key_from), 후보.model


def test_머리말에_적을_말에_세_설정이_다_든다():
    글 = CANDIDATES["claude-haiku-5-5"].describe()

    assert "temperature 보내지 않음" in 글
    assert "생각 기능 끔" in 글
    assert "JSON 응답 스키마로 강제" in 글
