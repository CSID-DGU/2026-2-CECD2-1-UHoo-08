"""예산 세트에서 제품 하나를 바꾼다. 동기 호출이다."""
import logging

from fastapi import APIRouter

from contracts.internal_api import BundleSwapRequest, BundleSwapResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/bundle/swap")
async def bundle_swap(req: BundleSwapRequest) -> BundleSwapResponse:
    # TODO: job 스냅샷에서 조합을 꺼내 한 자리를 바꾸고 총액을 다시 계산한다.
    logger.warning("stub: /bundle/swap job=%s slot=%s", req.job_id, req.slot)
    return BundleSwapResponse(stub=True)
