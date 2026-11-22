"""사진을 받아 다듬는 일이 지켜야 할 성질.

누운 사진을 그대로 보내면 모델이 누운 글자를 읽는다. 사진 주소에는 접근 토큰이 붙을 수
있어 오류 글에 남으면 안 된다.
"""
import io

import httpx
import pytest
from PIL import Image

from services import photo_loader
from services.photo_loader import PhotoError, fetch, load, prepare

_주소 = "https://storage.example.com/user-product-photos/u1/a.jpg?token=secret"


def _사진(크기=(300, 200), 색="red", 형식="JPEG", 모양="RGB", **저장값) -> bytes:
    담을_곳 = io.BytesIO()
    Image.new(모양, 크기, 색).save(담을_곳, format=형식, **저장값)
    return 담을_곳.getvalue()


def _열기(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# ── 다듬기 ────────────────────────────────────────────────────

def test_다듬은_사진은_JPEG다():
    결과 = prepare(_사진())
    assert 결과[:3] == b"\xff\xd8\xff"
    assert _열기(결과).format == "JPEG"


@pytest.mark.parametrize("크기, 기대", [
    ((4032, 3024), (2048, 1536)),   # 가로로 긴 휴대폰 사진
    ((3024, 4032), (1536, 2048)),   # 세로로 긴 사진
    ((2048, 1000), (2048, 1000)),   # 딱 상한
])
def test_긴_변을_상한까지_줄이고_비율은_지킨다(크기, 기대):
    assert _열기(prepare(_사진(크기))).size == 기대


def test_작은_사진은_키우지_않는다():
    assert _열기(prepare(_사진((640, 480)))).size == (640, 480)


def _왼쪽_빨강_오른쪽_파랑(방향: int) -> bytes:
    """가로 300, 세로 200. 왼쪽 절반은 빨강, 오른쪽 절반은 파랑. 파일 정보에 촬영 방향을 적는다."""
    사진 = Image.new("RGB", (300, 200), "red")
    사진.paste("blue", (150, 0, 300, 200))
    정보 = Image.Exif()
    정보[0x0112] = 방향
    담을_곳 = io.BytesIO()
    사진.save(담을_곳, format="JPEG", exif=정보, quality=95)
    return 담을_곳.getvalue()


def _색(사진: Image.Image, 위치: tuple[int, int]) -> str:
    빨강, _, 파랑 = 사진.getpixel(위치)
    return "빨강" if 빨강 > 파랑 else "파랑"


def test_촬영_방향대로_돌려_바로_세운다():
    """방향 6 은 시계 방향으로 90도 돌려야 바로 서는 사진이다. 왼쪽이 위로 온다."""
    결과 = _열기(prepare(_왼쪽_빨강_오른쪽_파랑(6)))
    assert 결과.size == (200, 300)
    assert (_색(결과, (100, 30)), _색(결과, (100, 270))) == ("빨강", "파랑")


def test_거꾸로_찍힌_사진도_바로_세운다():
    """방향 3 은 180도 돌려야 한다. 왼쪽과 오른쪽이 바뀐다."""
    결과 = _열기(prepare(_왼쪽_빨강_오른쪽_파랑(3)))
    assert 결과.size == (300, 200)
    assert (_색(결과, (30, 100)), _색(결과, (270, 100))) == ("파랑", "빨강")


def test_바로_선_사진은_돌리지_않는다():
    결과 = _열기(prepare(_왼쪽_빨강_오른쪽_파랑(1)))
    assert 결과.size == (300, 200)
    assert (_색(결과, (30, 100)), _색(결과, (270, 100))) == ("빨강", "파랑")


def test_파일_정보는_빠진다():
    """촬영 위치 같은 정보가 모델을 부르는 곳으로 나가지 않는다."""
    정보 = Image.Exif()
    정보[0x010F] = "PhoneMaker"
    정보[0x0112] = 6
    assert len(_열기(_사진(exif=정보)).getexif()) > 0

    assert len(_열기(prepare(_사진(exif=정보))).getexif()) == 0


@pytest.mark.parametrize("형식, 모양", [("PNG", "RGB"), ("WEBP", "RGB"), ("PNG", "P"), ("PNG", "L")])
def test_다른_형식도_JPEG로_바꾼다(형식, 모양):
    결과 = _열기(prepare(_사진((64, 48), 색=0 if 모양 in ("P", "L") else "green", 형식=형식, 모양=모양)))
    assert (결과.format, 결과.mode, 결과.size) == ("JPEG", "RGB", (64, 48))


def test_투명한_곳은_흰색으로_채운다():
    투명 = _사진((64, 48), 색=(0, 0, 0, 0), 형식="PNG", 모양="RGBA")
    assert min(_열기(prepare(투명)).getpixel((32, 24))) > 250


def test_HEIC_사진도_JPEG로_바꾼다():
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    결과 = _열기(prepare(_사진((64, 48), 색="green", 형식="HEIF")))
    assert (결과.format, 결과.size) == ("JPEG", (64, 48))


@pytest.mark.parametrize("data", [b"", b"not an image", b"<html>404</html>", _사진()[:200]])
def test_열_수_없는_사진은_오류다(data):
    with pytest.raises(PhotoError, match="열지 못했다"):
        prepare(data)


# ── 받기 ──────────────────────────────────────────────────────

@pytest.fixture
def 응답(monkeypatch):
    """사진 주소로 가는 요청을 가짜 응답으로 바꾼다. 받은 요청을 남긴다."""
    요청들: list[httpx.Request] = []

    def 세우기(만들기):
        def 처리(요청: httpx.Request) -> httpx.Response:
            요청들.append(요청)
            return 만들기(요청)

        monkeypatch.setattr(
            photo_loader, "_클라이언트",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(처리)),
        )
        return 요청들

    return 세우기


@pytest.mark.asyncio
async def test_주소의_사진을_받는다(응답):
    요청들 = 응답(lambda 요청: httpx.Response(200, content=b"photo-bytes"))

    assert await fetch(_주소) == b"photo-bytes"
    assert [str(요청.url) for 요청 in 요청들] == [_주소]


@pytest.mark.asyncio
@pytest.mark.parametrize("코드", [302, 403, 404, 500])
async def test_사진이_오지_않으면_오류다(응답, 코드):
    응답(lambda 요청: httpx.Response(코드, content=b"x"))

    with pytest.raises(PhotoError, match=str(코드)):
        await fetch(_주소)


@pytest.mark.asyncio
async def test_빈_응답은_오류다(응답):
    응답(lambda 요청: httpx.Response(200, content=b""))

    with pytest.raises(PhotoError, match="빈 사진"):
        await fetch(_주소)


@pytest.mark.asyncio
async def test_크기가_상한을_넘는다고_적혀_있으면_받지_않는다(응답, monkeypatch):
    monkeypatch.setattr(photo_loader, "최대_바이트", 100)
    응답(lambda 요청: httpx.Response(200, content=b"x" * 101))

    with pytest.raises(PhotoError, match="너무 크다"):
        await fetch(_주소)


@pytest.mark.asyncio
async def test_크기가_적혀_있지_않아도_상한을_넘으면_그만_받는다(응답, monkeypatch):
    monkeypatch.setattr(photo_loader, "최대_바이트", 100)
    보낸: list[int] = []

    async def 조각들():
        for 번호 in range(10):
            보낸.append(번호)
            yield b"x" * 40

    응답(lambda 요청: httpx.Response(200, content=조각들()))

    with pytest.raises(PhotoError, match="너무 크다"):
        await fetch(_주소)
    assert len(보낸) < 10


@pytest.mark.asyncio
async def test_상한과_같은_크기는_받는다(응답, monkeypatch):
    monkeypatch.setattr(photo_loader, "최대_바이트", 100)
    응답(lambda 요청: httpx.Response(200, content=b"x" * 100))

    assert len(await fetch(_주소)) == 100


def _연결_실패(요청: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(f"연결 실패: {요청.url}", request=요청)


def _시간_초과(요청: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout(f"시간 초과: {요청.url}", request=요청)


@pytest.mark.asyncio
@pytest.mark.parametrize("실패", [_연결_실패, _시간_초과], ids=["연결 실패", "시간 초과"])
async def test_받다가_실패하면_오류다(응답, 실패):
    응답(실패)

    with pytest.raises(PhotoError, match="받지 못했다"):
        await fetch(_주소)


@pytest.mark.asyncio
@pytest.mark.parametrize("주소", ["not a url", "ftp://storage.example.com/a.jpg", ""])
async def test_주소가_잘못되면_오류다(주소):
    with pytest.raises(PhotoError, match="받지 못했다"):
        await fetch(주소)


@pytest.mark.asyncio
@pytest.mark.parametrize("만들기", [
    lambda 요청: httpx.Response(404, content=b"x"),
    _연결_실패,
    _시간_초과,
], ids=["404", "연결 실패", "시간 초과"])
async def test_오류에_사진_주소가_남지_않는다(응답, 만들기):
    """서명된 주소에는 접근 토큰이 붙어 있다. 이어진 원래 오류에도 주소가 들어 있어 잇지 않는다."""
    응답(만들기)

    with pytest.raises(PhotoError) as 잡힌:
        await fetch(_주소)
    오류 = 잡힌.value
    assert "secret" not in str(오류) and "storage.example.com" not in str(오류)
    # 원래 오류가 이어져 있으면 스택을 남길 때 함께 찍힌다
    assert 오류.__cause__ is None
    assert 오류.__context__ is None or 오류.__suppress_context__


# ── 받아서 다듬기 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_주소의_사진을_받아_다듬는다(응답):
    응답(lambda 요청: httpx.Response(200, content=_왼쪽_빨강_오른쪽_파랑(6)))

    결과 = _열기(await load(_주소))
    assert (결과.format, 결과.size) == ("JPEG", (200, 300))


@pytest.mark.asyncio
async def test_사진이_아닌_것을_받으면_오류다(응답):
    응답(lambda 요청: httpx.Response(200, content=b"<html>error</html>"))

    with pytest.raises(PhotoError, match="열지 못했다"):
        await load(_주소)
