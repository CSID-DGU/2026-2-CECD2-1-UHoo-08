package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Summary;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.RecommendationCategory;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class SummaryBuilderTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode json(String value) throws Exception {
        return MAPPER.readTree(value);
    }

    @Test
    void 내_피부_기준은_피부_타입과_맨_앞_조건_하나로_기준_문구를_만든다() throws Exception {
        Summary summary = SummaryBuilder.build(
                json("{\"category\":\"base\",\"conditions\":[\"여름\",\"매트\",\"쿠션\"],\"budgetMax\":30000}"),
                12, RecommendationBasis.SELF, "OILY", MissingNode.getInstance());

        assertThat(summary.getCategoryLabel()).isEqualTo("베이스 메이크업");
        assertThat(summary.getTotalCount()).isEqualTo(12);
        assertThat(summary.getBasisLabel()).isEqualTo("지성 · 여름 기준");
        assertThat(summary.getConditions()).containsExactly("여름", "매트", "쿠션", "3만원 이하");
        assertThat(summary.getNotice()).isNull();
    }

    @Test
    void 피부_타입도_조건도_없으면_내_피부_기준이다() throws Exception {
        assertThat(SummaryBuilder.build(json("{}"), 0, RecommendationBasis.SELF, null, MissingNode.getInstance())
                .getBasisLabel()).isEqualTo("내 피부 기준");
    }

    @Test
    void 인기_기준은_최근_30일_기준이다() throws Exception {
        assertThat(SummaryBuilder.build(json("{\"conditions\":[\"여름\"]}"), 3, RecommendationBasis.POPULAR, "OILY",
                MissingNode.getInstance()).getBasisLabel()).isEqualTo("최근 30일 기준");
    }

    @Test
    void 다른_사람_기준은_쓰실_분의_관계와_피부_타입으로_만든다() throws Exception {
        assertThat(SummaryBuilder.build(json("{}"), 3, RecommendationBasis.OTHER, "OILY",
                json("{\"relation\":\"MOM\",\"skinType\":\"DRY\"}")).getBasisLabel()).isEqualTo("엄마 · 건성 기준");
        assertThat(SummaryBuilder.build(json("{}"), 3, RecommendationBasis.OTHER, null,
                json("{\"relation\":\"CUSTOM\"}")).getBasisLabel()).isEqualTo("다른 분 기준");
    }

    @Test
    void 카테고리가_비었거나_모르는_값이면_null이다() throws Exception {
        assertThat(SummaryBuilder.build(json("{\"category\":null}"), 0, RecommendationBasis.SELF, null,
                MissingNode.getInstance()).getCategoryLabel()).isNull();
        assertThat(RecommendationCategory.labelOf("blush")).isNull();
        assertThat(RecommendationCategory.labelOf(null)).isNull();
        assertThat(RecommendationCategory.labelOf("sun")).isEqualTo("선케어");
    }

    @Test
    void 세트_예산은_총액_문구로_붙인다() throws Exception {
        assertThat(SummaryBuilder.conditions(json("{\"conditions\":[],\"budgetTotal\":100000}")))
                .containsExactly("총 10만원");
    }

    @Test
    void 가성비_요청이면_가성비_안내를_환경_요청이면_환경_안내를_보인다() throws Exception {
        assertThat(SummaryBuilder.notice(json("{\"valueSeeking\":true,\"useEnv\":true}")))
                .isEqualTo("가격 대비 효능과 후기를 함께 보고 골랐어요");
        assertThat(SummaryBuilder.notice(json("{\"useEnv\":true}")))
                .isEqualTo("요즘 지내시는 곳의 날씨와 공기를 함께 반영했어요");
        assertThat(SummaryBuilder.notice(json("{}"))).isNull();
    }

    @ParameterizedTest
    @CsvSource({
            "30000, 3만원",
            "35000, 3.5만원",
            "100000, 10만원",
            "5000, '5,000원'",
            "12345, '12,345원'",
    })
    void 금액은_만원_단위로_줄여_쓴다(long amount, String expected) {
        assertThat(SummaryBuilder.won(amount)).isEqualTo(expected);
    }
}
