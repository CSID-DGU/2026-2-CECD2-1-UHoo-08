"""광고 1차 규칙. 판정 기준은 eval/prompts/trend_ad_v1.md."""
import pytest

from rules.ad_disclosure import AD, ORGANIC, UNSURE, classify, split_legend


def rules_of(result: dict) -> set[str]:
    return {h["rule"] for h in result["hits"]}


@pytest.mark.parametrize("caption", [
    "#광고 이번 신상 쿠션 써봤어요",
    "가을 립 조합 *광고",
    "몽글몽글한 블러셔 광고*",
    "(광고) #댓글이벤트 누디 메이크업",
    "[광고] 로션 찾는 사람?",
    "#유료광고 무화과 메이크업",
    "앰플 2주 써봤어요\n\n광고  brand_official\n\n#앰플",
    "저장하세요 할인 소식을 담은 #광고 를 포함하고 있으나 직접 고른 제품만",
])
def test_광고_표기_변형을_잡는다(caption):
    assert classify(caption)["verdict"] == AD


@pytest.mark.parametrize("caption", [
    "#제품제공 가을 립 조합",
    "스킨케어 유목민을 위한 [제품제공]",
    "신상 블러셔(단순선물제공) 너무 예뻐요",
    "※ 제품 무료 제공 (콘텐츠 업로드 및 노출 의무 없음)",
    "#🎁 출시 전부터 기다린 치크",
])
def test_제공_표기는_광고다(caption):
    result = classify(caption)
    assert result["verdict"] == AD
    assert any(r.startswith("gifted.") for r in rules_of(result))


def test_광고_아님이라고_밝히면_광고가_아니다():
    result = classify("(광고 아님) 진짜 너무 좋아서 급하게 올림")
    assert result["verdict"] == ORGANIC
    assert "negation.not_ad" in rules_of(result)
    assert not any(r.startswith("disclosure.") for r in rules_of(result))


def test_내돈내산은_광고가_아니다():
    assert classify("(내돈내산) 일본 가면 꼭 사와야 하는 블러셔")["verdict"] == ORGANIC


def test_광고_표기가_있으면_본문의_내돈내산보다_우선한다():
    caption = "(이벤트)#광고 세미매트 쿠션 추천\n여름에 내돈내산 했던 그 쿠션 기억나시나요"
    assert classify(caption)["verdict"] == AD


LEGEND = (
    "📘 직접 구매한 제품\n"
    "📗 영상 노출 의무 없이, 제품무상제공\n"
    "📙 원고료를 지급받은 유료광고 제품\n\n"
)


def test_범례에_제공_아이콘이_쓰이면_광고다():
    caption = LEGEND + "📘 A사 - 렌즈\n📗 B사 - 토너패드\n📘 C사 - 세럼"
    result = classify(caption)
    assert result["verdict"] == AD
    assert "legend.sponsored" in rules_of(result)


def test_범례만_있고_전부_직접_구매면_광고가_아니다():
    caption = LEGEND + "📘 피규어 A\n📘 피규어 B\n📘 키링 C"
    result = classify(caption)
    assert result["verdict"] == ORGANIC
    # 범례 줄의 "유료광고"·"원고료"를 광고 표기로 세지 않는다
    assert not any(r.startswith("disclosure.") for r in rules_of(result))


def test_범례가_아닌_한_줄짜리_아이콘_문장은_범례로_보지_않는다():
    body, legend = split_legend("🎁 증정 이벤트 진행 중\n📍 신청 기간 10/16~10/19")
    assert legend == {}


def test_본인_브랜드를_말하면_광고다():
    result = classify("러플 카카오톡 선물하기 OPEN!! 24시간 특가", owned_brands=["러브플레르", "러플"])
    assert result["verdict"] == AD
    assert {"rule": "own_brand", "text": "러플"} in result["hits"]


def test_남의_계정이면_같은_브랜드를_말해도_본인_브랜드가_아니다():
    result = classify("요즘 쓰는 러브플레르 립라이너")
    assert "own_brand" not in rules_of(result)


@pytest.mark.parametrize("caption", [
    "📍공구 일정 10/16 오후 5시 ~ 10/19",
    "[하객룩] 댓글 다시면 링크 보내드릴게요!",
    "[일본] 이라고 남겨주면 링크 발송됩니다!",
    "댓글 달아주시면 할인 링크 보내드려요",
    "패드 할인 목요일에 끝나니까 부지런히 구매들 하셔\n(프로필 링크)",
])
def test_공구와_링크_DM은_광고다(caption):
    result = classify(caption)
    assert result["verdict"] == AD
    assert any(r.startswith("affiliate.") for r in rules_of(result))


def test_프로필_링크가_유튜브_안내면_광고가_아니다():
    caption = "품절을 뚫고 겨우 구매했어요 유튜브에 긴 영상 있어요 프로필링크 타고 오셔유"
    assert "affiliate.profile_link" not in rules_of(classify(caption))


def test_상업_신호만_있으면_모름으로_넘긴다():
    result = classify("올리브영 단독 기획세트, 본품에 미니 증정까지! 오특 놓치지 마세요")
    assert result["verdict"] == UNSURE
    assert result["is_ad"] is None


def test_신호가_없으면_광고가_아니다():
    result = classify("노란 옷 입고 노란 커피 마시구")
    assert result == {"verdict": ORGANIC, "is_ad": False, "hits": [], "version": result["version"]}


def test_캡션이_없어도_판정한다():
    assert classify(None)["verdict"] == ORGANIC
    assert classify("")["verdict"] == ORGANIC


def test_입력이_같으면_출력이_같다():
    caption = LEGEND + "📗 B사 - 토너패드 #광고 오특 쿠폰"
    assert classify(caption, ["x"]) == classify(caption, ["x"])
