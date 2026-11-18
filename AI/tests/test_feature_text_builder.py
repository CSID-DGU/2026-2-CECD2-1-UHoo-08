"""feature_text_builder 단위 테스트."""
import pytest

from services.feature_text_builder import build_product_text


class TestFeatureTextBuilder:
    def test_base_full(self):
        text = build_product_text("base", {
            "product_type": "쿠션",
            "coverage": "중간",
            "finish": "세미매트",
            "skin_type": "지성",
            "skin_concern": ["모공", "잡티"],
            "personal_color": "웜톤",
            "lasting_power": "높음",
            "spf": "SPF50+/PA+++",
        })
        assert "쿠션 제품" in text
        assert "커버력이 중간" in text
        assert "세미매트" in text
        assert "지성 피부" in text
        assert "모공·잡티" in text
        assert "웜톤" in text
        assert "SPF50+/PA+++" in text

    def test_base_null_fields_skipped(self):
        text = build_product_text("base", {
            "product_type": "쿠션",
            "coverage": None,
            "spf": None,
        })
        assert "쿠션" in text
        assert "커버력" not in text
        assert "SPF" not in text

    def test_sun_with_white_cast(self):
        text = build_product_text("sun", {
            "product_type": "선크림",
            "spf": "SPF50+",
            "pa": "PA++++",
            "white_cast": False,
        })
        assert "선크림" in text
        assert "SPF50+" in text
        assert "PA++++" in text
        assert "백탁 없음" in text

    def test_sun_white_cast_true(self):
        text = build_product_text("sun", {
            "product_type": "선스틱",
            "white_cast": True,
        })
        assert "백탁 있음" in text

    def test_lip_with_moisturizing(self):
        text = build_product_text("lip", {
            "product_type": "틴트",
            "finish": "글로우",
            "moisturizing": True,
        })
        assert "틴트" in text
        assert "글로우" in text
        assert "보습력 있음" in text

    def test_skincare_with_ingredients(self):
        text = build_product_text("skincare", {
            "product_type": "세럼",
            "texture": "가벼운",
            "key_ingredient": ["히알루론산", "나이아신아마이드"],
            "fragrance_free": True,
        })
        assert "세럼" in text
        assert "가벼운 제형" in text
        assert "히알루론산·나이아신아마이드" in text
        assert "무향 제품" in text

    def test_skincare_with_fragrance(self):
        text = build_product_text("skincare", {
            "product_type": "토너",
            "fragrance_free": False,
        })
        assert "무향 아님" in text

    def test_eye(self):
        text = build_product_text("eye", {
            "product_type": "아이라이너",
            "finish": "매트",
            "lasting_power": "높음",
            "waterproof": True,
        })
        assert text == "아이라이너 제품. 매트 마무리감. 지속력 높음. 워터프루프."

    def test_cheek(self):
        text = build_product_text("cheek", {
            "product_type": "블러셔",
            "finish": "글로우",
            "personal_color": "쿨톤",
            "lasting_power": None,
        })
        assert text == "블러셔 제품. 글로우 마무리감. 쿨톤에 어울림."

    def test_product_type_list_writes_both(self):
        text = build_product_text("lip", {"product_type": ["립세럼", "틴트"]})
        assert text.startswith("립세럼, 틴트 제품")

    def test_product_type_synonym_written_as_standard_name(self):
        assert build_product_text("skincare", {"product_type": "스킨"}).startswith("토너 제품")
        assert build_product_text("cheek", {"product_type": ["블러쉬", "블러셔"]}).startswith("블러셔 제품")

    def test_unlisted_product_type_kept_as_is(self):
        assert build_product_text("skincare", {"product_type": "핸드크림"}).startswith("핸드크림 제품")

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError):
            build_product_text("makeup_remover", {})

    def test_empty_feature_returns_empty(self):
        text = build_product_text("base", {})
        assert text == ""