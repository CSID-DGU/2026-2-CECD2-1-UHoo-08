"""서버 진입점마다 v2 경로가 붙어 있는지 본다.

운영 이미지는 main.py 로, 개발 서버는 app/main.py 로 뜬다. v2 경로를 한쪽에만
붙이면 다른 쪽에서는 BE 호출이 404 로 끝나는데, 진입점 테스트가 없으면 배포
뒤에야 드러난다.

진입점은 config 를 import 해서 API 키가 없으면 뜨지 않으므로, 실행하지 않고
소스만 읽어 확인한다.
"""
import ast
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINTS = ["main.py", "app/main.py"]


def _v2_라우터_이름(tree: ast.Module) -> str | None:
    """`from api.internal.v2 import router as X` 의 X 를 찾는다."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "api.internal.v2":
            for alias in node.names:
                if alias.name == "router":
                    return alias.asname or alias.name
    return None


def _붙인_접두어(tree: ast.Module, 이름: str) -> list[str | None]:
    """`app.include_router(이름, prefix=...)` 호출의 prefix 를 모은다."""
    접두어 = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == 이름):
            continue
        prefix = next((kw.value for kw in node.keywords if kw.arg == "prefix"), None)
        접두어.append(prefix.value if isinstance(prefix, ast.Constant) else None)
    return 접두어


@pytest.mark.parametrize("rel", ENTRYPOINTS)
def test_v2_경로가_internal_아래_붙어_있다(rel):
    tree = ast.parse((AI_ROOT / rel).read_text(encoding="utf-8"))

    이름 = _v2_라우터_이름(tree)
    assert 이름, f"{rel} 이 v2 라우터를 import 하지 않는다"
    assert _붙인_접두어(tree, 이름) == ["/internal"], f"{rel} 에 v2 라우터가 /internal 로 붙어 있지 않다"
