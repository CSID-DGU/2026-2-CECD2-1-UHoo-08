"""사진 두 장으로 보유 제품을 인식한다."""
import logging

from fastapi import APIRouter

from contracts.internal_api import RecognizePhotosRequest, RecognizePhotosResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/products/recognize-photos")
async def recognize_photos(req: RecognizePhotosRequest) -> RecognizePhotosResponse:
    # TODO: 제품명 면은 VLM 으로 읽어 마스터와 매칭하고,
    #       기한 면은 날짜·PAO·제조일을 뽑는다. 못 읽은 값은 비워 둔다.
    #
    # 이미지 URL 은 로그에 남기지 않는다. 서명 URL 이면 query string 에 접근
    # 토큰이 붙어 있어, 로그를 모으는 쪽으로 그대로 흘러간다.
    logger.warning(
        "stub: /products/recognize-photos (기한 사진 %s)",
        "있음" if req.date_image else "없음",
    )
    return RecognizePhotosResponse(stub=True)
