"""GraphState 가 지켜야 할 성질.

키 이름 규칙을 어기면 BE·FE로 나가는 camelCase 와 섞여, 어느 쪽 이름인지
매번 확인해야 한다. 값이 늘어날수록 되돌리기 어려워지므로 여기서 막는다.
"""
import re

from graph.state import GraphState

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_부분_갱신이_허용된다():
    """노드는 바꾼 키만 돌려준다. total=True 면 전체 키를 요구한다."""
    assert GraphState.__total__ is False


def test_키가_모두_snake_case_다():
    나쁜_키 = [k for k in GraphState.__annotations__ if not SNAKE_CASE.match(k)]
    assert 나쁜_키 == [], f"snake_case 가 아닌 키: {나쁜_키}"


def test_파이프라인_필수_키가_있다():
    """노드 계약이 기대하는 최소 키. 이름을 바꾸면 여기서 걸린다."""
    필수 = {
        "job_id", "user_id", "raw_query", "query_spec", "scenario",
        "user_profile", "inventory", "candidates", "excluded", "scored",
        "result", "trace",
    }
    assert 필수 <= set(GraphState.__annotations__)
