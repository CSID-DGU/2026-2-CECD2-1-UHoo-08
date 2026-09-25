"""StateGraph 노드.

노드 하나가 파일 하나다. 파일 이름이 레지스트리(graph/registry.py)에 적는
단계 이름이 된다.

    async def <파일명>(state: GraphState) -> dict

반환 dict에는 바꾼 키만 담고, 파일 상단 docstring에 READS: / WRITES: 를 적는다.
자세한 내용은 AI/README.md 를 본다.
"""
