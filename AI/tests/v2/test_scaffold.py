"""v2 구조 규칙이 지켜지는지 검사한다.

노드 파일은 서로 다른 파트가 각자 추가하므로, 규칙을 문서로만 두면 곧 흩어진다.
여기서 기계로 검사해 PR 단계에서 걸리게 한다.
"""
import ast
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parents[2]
NODES_DIR = AI_ROOT / "graph" / "nodes"

REQUIRED_DIRS = [
    "contracts",
    "graph/nodes",
    "scorers",
    "rules",
    # 합성 데이터는 만드는 대상별로 나눈다.
    "data/synthetic/personas",
    "data/synthetic/queries",
    "data/synthetic/feedback",
    "data/synthetic/env",
    # 골든셋은 무엇을 평가하는지로 나눈다.
    "eval/golden/router",
    "eval/golden/scenario",
    "eval/golden/recognize",
    "eval/golden/compatibility",
    "eval/golden/env",
    "eval/golden/bundle",
    "eval/golden/trend",
    "eval/prompts",
    "eval/assets",
    "eval/reports",
]


@pytest.mark.parametrize("rel", REQUIRED_DIRS)
def test_v2_디렉터리가_존재한다(rel):
    assert (AI_ROOT / rel).is_dir(), f"{rel} 디렉터리가 없다"


def _node_files():
    return sorted(p for p in NODES_DIR.glob("*.py") if p.name != "__init__.py")


def _node_function(tree, name):
    for stmt in tree.body:
        if isinstance(stmt, ast.AsyncFunctionDef) and stmt.name == name:
            return stmt
    return None


@pytest.mark.parametrize("path", _node_files(), ids=lambda p: p.name)
def test_노드가_계약을_지킨다(path):
    """파일명과 같은 async 함수 하나, 인자는 state 하나, READS/WRITES 명시."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    name = path.stem

    doc = ast.get_docstring(tree) or ""
    assert "READS:" in doc and "WRITES:" in doc, (
        f"{path.name}: 파일 상단 docstring에 READS: / WRITES: 를 적어야 한다"
    )

    fn = _node_function(tree, name)
    assert fn is not None, f"{path.name}: `async def {name}(state)` 가 없다"

    args = fn.args
    assert (
        [a.arg for a in args.posonlyargs + args.args] == ["state"]
        and not args.vararg
        and not args.kwonlyargs
        and not args.kwarg
    ), f"{path.name}: 인자는 state 하나여야 한다 (현재 {ast.unparse(args)})"
