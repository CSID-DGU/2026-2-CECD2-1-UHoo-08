"""v2 내부 API.

아직 내용이 없는 경로는 stub 으로 열어 둔다. BE 가 호출부·저장·조회를 먼저
완성하고, AI 가 내용을 채우면 그대로 이어진다.

이 패키지의 모듈은 config 나 DB 를 import 하지 않는다. 계약과 FastAPI 만
있으면 되므로, 키 없이도 뜨고 CI 에서도 그대로 돈다. 실제 구현이 들어올 때
그 모듈만 무거워진다.
"""
from fastapi import APIRouter

from api.internal.v2 import agent, bundle, feedback, home, products, trends

router = APIRouter()
for _하위 in (agent, products, home, bundle, trends, feedback):
    router.include_router(_하위.router)
