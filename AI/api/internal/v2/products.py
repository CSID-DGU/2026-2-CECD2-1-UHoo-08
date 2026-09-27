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
    logger.warning("stub: /products/recognize-photos name=%s", req.name_image)
    return RecognizePhotosResponse(stub=True)
