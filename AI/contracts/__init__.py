"""여러 파트가 같이 읽는 값의 모양을 정의하는 pydantic 스키마.

여기를 바꾸면 이 값을 쓰는 다른 코드가 같이 깨진다. 수정할 때는 이슈를 먼저 연다.

    query_spec.py  Normalize 출력 = Router 입력
    result.py      Compose 출력 = BE 저장값 = FE 렌더값
    score.py       Score 출력과 scorer 플러그인 인터페이스
"""
