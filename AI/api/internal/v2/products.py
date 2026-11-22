"""제품명 면과 기한 면 사진으로 보유 제품을 인식한다. 화면이 바로 기다리는 호출이다.

읽지 못한 값은 비워서 돌려준다. 후보가 없거나 기한이 비어 있어도 오류가 아니다.

실패는 상태 코드로 알린다. 빈 결과로 덮으면 BE 가 읽을 글자가 없는 사진으로 읽고,
사용자에게 다시 찍으라는 대신 이름으로 찾으라고 안내한다.

    422   사진을 받지 못했거나 열지 못했다
    502   사진 모델의 답을 쓸 수 없다
    500   그 밖의 실패. 모델 호출이나 상품 목록 조회가 실패했다

사진 주소는 로그와 오류 응답에 남기지 않는다. 서명 주소면 query string 에 접근 토큰이
붙어 있어, 로그를 모으는 쪽으로 그대로 흘러간다.
"""
import logging

from fastapi import APIRouter, HTTPException

from contracts.internal_api import RecognizePhotosRequest, RecognizePhotosResponse
from services import photo_recognizer
from services.photo_loader import PhotoError
from services.photo_recognizer import RecognizeError

logger = logging.getLogger(__name__)
router = APIRouter()

_사진_오류 = 422
_모델_답_오류 = 502
_그_밖의_오류 = 500


def _받은_면(req: RecognizePhotosRequest) -> str:
    """로그에 남길 말. 어느 면을 읽다가 실패했는지 알 수 있게 한다."""
    if req.name_image and req.date_image:
        return "제품명 면, 기한 면"
    return "제품명 면" if req.name_image else "기한 면"


@router.post("/products/recognize-photos")
async def recognize_photos(req: RecognizePhotosRequest) -> RecognizePhotosResponse:
    try:
        return await photo_recognizer.recognize(req.name_image, req.date_image)
    except PhotoError as 오류:
        logger.warning("사진 인식 실패 (%s): %s", _받은_면(req), 오류)
        raise HTTPException(status_code=_사진_오류, detail=str(오류)) from None
    except RecognizeError as 오류:
        logger.warning("사진 인식 실패 (%s): %s", _받은_면(req), 오류)
        raise HTTPException(status_code=_모델_답_오류, detail=str(오류)) from None
    except Exception:
        # BE 는 사용자에게 인식 실패라고만 알린다. 원인은 여기서 스택과 함께 남긴다
        logger.exception("사진 인식 실패 (%s)", _받은_면(req))
        raise HTTPException(status_code=_그_밖의_오류, detail="사진을 인식하지 못했다") from None
