"""날씨를 볼 지역 고르기. DB 없이 돈다."""
from services.iot.user_region import resolve

지역들 = {"서울", "인천", "부산", "전남광주"}


def _고르기(region, user_id, 저장된=None, 터짐=False):
    def lookup(uid):
        if 터짐:
            raise RuntimeError("DB 실패")
        return 저장된
    return resolve(region, user_id, known=지역들, default="인천", lookup=lookup)


def test_요청에_지역이_있으면_그_지역이다():
    assert _고르기("부산", "u1", 저장된="서울") == "부산"


def test_지역이_없으면_사용자가_설정한_지역이다():
    """앱은 user_id 만 보낸다. 지역을 바꿨는데 계속 인천으로 나오던 문제."""
    assert _고르기(None, "u1", 저장된="서울") == "서울"
    assert _고르기("  ", "u1", 저장된="전남광주") == "전남광주"


def test_사용자도_지역도_없으면_기본_지역이다():
    # 키오스크는 user_id 없이 부른다
    assert _고르기(None, None) == "인천"
    assert _고르기(None, "u1", 저장된=None) == "인천"


def test_모르는_지역이거나_조회가_실패해도_날씨는_기본_지역으로_뜬다():
    assert _고르기(None, "u1", 저장된="고양시") == "인천"
    assert _고르기(None, "u1", 터짐=True) == "인천"


def test_사용자_조회는_지역이_없을_때만_한다():
    불렀다 = []

    def lookup(uid):
        불렀다.append(uid)
        return "서울"
    resolve("부산", "u1", known=지역들, default="인천", lookup=lookup)
    assert 불렀다 == []
