"""인식할 사진을 받아 사진 모델에 보낼 모양으로 다듬는다.

BE 는 사용자가 찍은 사진을 저장소에 올리고 그 주소를 보낸다. 휴대폰 사진은 그대로 보내기에
맞지 않는 점이 셋 있다.

    방향    세로로 찍은 사진은 누운 채로 저장되고, 돌려야 할 방향만 파일 정보에 적힌다.
            그대로 보내면 모델이 누운 글자를 읽는다
    크기    수천만 화소라 요청이 커지고, 모델은 어차피 줄여서 본다
    형식    아이폰의 HEIC 는 받지 않는 모델이 있다

그래서 방향대로 돌려 바로 세우고, 긴 변을 줄이고, JPEG 로 다시 저장해 보낸다. 다시 저장하면
촬영 위치 같은 파일 정보도 빠진다.

사진 주소는 오류 글에 담지 않는다. 서명된 주소면 접근 토큰이 붙어 있어, 오류를 남기는
로그로 그대로 흘러간다.

httpx 와 Pillow 는 부를 일이 생긴 뒤에 가져온다.
"""
from __future__ import annotations

import asyncio
import io
from typing import Any

# 받는 사진의 최대 크기. BE 가 사진을 올릴 때 받는 상한과 같다
최대_바이트 = 10 * 1024 * 1024
# 사진을 받을 때 기다리는 시간(초). 연결까지, 그리고 응답을 받는 동안
잇는_시간 = 5.0
받는_시간 = 15.0
# 다듬은 사진의 긴 변(픽셀). 이보다 크면 줄인다
최대_변 = 2048
# JPEG 로 저장할 때의 품질
저장_품질 = 90


class PhotoError(Exception):
    """사진을 받지 못했거나 열지 못했다."""


def _클라이언트() -> Any:
    import httpx

    return httpx.AsyncClient(timeout=httpx.Timeout(받는_시간, connect=잇는_시간))


async def fetch(url: str) -> bytes:
    """주소에서 사진을 내려받는다. 받지 못하면 PhotoError."""
    import httpx

    조각들: list[bytes] = []
    받은 = 0
    try:
        async with _클라이언트() as 클라이언트, 클라이언트.stream("GET", url) as 응답:
            if 응답.status_code != 200:
                raise PhotoError(f"사진을 받지 못했다 (응답 {응답.status_code})")
            적힌_크기 = 응답.headers.get("content-length", "")
            if 적힌_크기.isdigit() and int(적힌_크기) > 최대_바이트:
                raise PhotoError("사진이 너무 크다")
            async for 조각 in 응답.aiter_bytes():
                받은 += len(조각)
                if 받은 > 최대_바이트:
                    raise PhotoError("사진이 너무 크다")
                조각들.append(조각)
    except (httpx.HTTPError, httpx.InvalidURL) as 오류:
        # httpx 의 오류 글에는 주소가 들어 있다. 종류만 남기고 원래 오류는 잇지 않는다
        raise PhotoError(f"사진을 받지 못했다 ({type(오류).__name__})") from None
    if not 받은:
        raise PhotoError("빈 사진이다")
    return b"".join(조각들)


def _HEIC_열기() -> None:
    """Pillow 가 HEIC 를 열 수 있게 한다. pillow-heif 가 없으면 HEIC 만 열지 못한다."""
    try:
        import pillow_heif
    except ImportError:
        return
    pillow_heif.register_heif_opener()


def _RGB로(사진: Any) -> Any:
    """JPEG 로 저장할 수 있는 색 모양으로 바꾼다. 투명한 곳은 흰색으로 채운다."""
    from PIL import Image

    if 사진.mode in ("RGBA", "LA") or (사진.mode == "P" and "transparency" in 사진.info):
        겹칠 = 사진.convert("RGBA")
        바탕 = Image.new("RGB", 겹칠.size, "white")
        바탕.paste(겹칠, mask=겹칠.getchannel("A"))
        return 바탕
    return 사진.convert("RGB")


def prepare(data: bytes) -> bytes:
    """사진을 바로 세우고, 줄이고, JPEG 로 바꾼 바이트를 돌려준다. 열지 못하면 PhotoError."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    _HEIC_열기()
    담을_곳 = io.BytesIO()
    try:
        with Image.open(io.BytesIO(data)) as 원본:
            사진 = _RGB로(ImageOps.exif_transpose(원본))
            사진.thumbnail((최대_변, 최대_변), Image.Resampling.LANCZOS)
            사진.save(담을_곳, format="JPEG", quality=저장_품질)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as 오류:
        raise PhotoError(f"사진을 열지 못했다 ({type(오류).__name__})") from None
    return 담을_곳.getvalue()


async def load(url: str) -> bytes:
    """주소의 사진을 받아 다듬은 JPEG 바이트를 돌려준다."""
    return await asyncio.to_thread(prepare, await fetch(url))
