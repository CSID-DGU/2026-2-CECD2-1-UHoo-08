package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Alternative;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Bundle;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.ExcludedItem;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Item;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Slot;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.service.ResultAssembler.Source;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class ResultAssemblerTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final UUID JOB_ID = UUID.randomUUID();

    private static JsonNode sample(String scenario) throws IOException {
        try (InputStream in = ResultAssemblerTest.class.getResourceAsStream("/ai-results/" + scenario + ".json")) {
            return MAPPER.readTree(in);
        }
    }

    private static Product product(String id, Integer originalPrice, String averageScore, Integer reviewCount) {
        return Product.builder().id(UUID.fromString(id)).name("상품").brand("브랜드").category("base")
                .originalPrice(originalPrice)
                .averageScore(averageScore == null ? null : new BigDecimal(averageScore))
                .reviewCount(reviewCount).build();
    }

    private static RecommendationResultV2Response assemble(String scenario, RecommendationBasis basis,
                                                           Map<String, Product> products) throws IOException {
        Source source = new Source(JOB_ID, null, scenario, basis, sample(scenario), MissingNode.getInstance(),
                "OILY", MissingNode.getInstance());
        return ResultAssembler.assemble(source, products, null);
    }

    @Test
    void 검색_결과는_목록과_상단_문구와_제외_목록을_명세_모양으로_옮긴다() throws IOException {
        RecommendationResultV2Response result = assemble("S2_SEARCH", RecommendationBasis.SELF,
                Map.of("22222222-2222-2222-2222-222222222222", product("22222222-2222-2222-2222-222222222222", 31000, "4.5", 100)));

        assertThat(result.getJobId()).isEqualTo(JOB_ID);
        assertThat(result.getScenario()).isEqualTo("S2_SEARCH");
        assertThat(result.getBasis()).isEqualTo(RecommendationBasis.SELF);
        assertThat(result.getSummary().getCategoryLabel()).isEqualTo("베이스 메이크업");
        assertThat(result.getSummary().getTotalCount()).isEqualTo(2);
        assertThat(result.getSummary().getBasisLabel()).isEqualTo("지성 · 여름 기준");
        assertThat(result.getSummary().getConditions()).containsExactly("여름", "매트", "쿠션", "3만원 이하");
        assertThat(result.getAppliedPreference()).isNull();

        Item first = result.getItems().get(0);
        assertThat(first.getProductId()).isEqualTo("11111111-1111-1111-1111-111111111111");
        assertThat(first.getPrice()).isEqualTo(28000);
        assertThat(first.getTotalScore()).isEqualTo(85);
        assertThat(first.getRating()).isNull();
        assertThat(first.getBreakdown()).extracting("key", "score", "weight")
                .containsExactly(tuple("personalization", 93.0, 0.35), tuple("budget_fit", 87.5, 0.15));
        assertThat(first.getBadges()).extracting("type").containsExactly("CONFLICT_SEPARATE");
        assertThat(first.getReason()).startsWith("지성 피부에");

        // AI 가 가격을 비워 두면 정가로 채운다
        assertThat(result.getItems().get(1).getPrice()).isEqualTo(31000);

        assertThat(result.getExcluded().getCount()).isEqualTo(2);
        assertThat(result.getExcluded().getItems()).extracting(ExcludedItem::getReason).containsExactly("OWNED", "CONFLICT");
        assertThat(result.getSimilarUserProducts()).extracting("name", "price").containsExactly(tuple("세미매트 쿠션", 45000));
        assertThat(result.getAlternatives()).isEmpty();
        assertThat(result.getAlternativesDroppedCount()).isZero();
        assertThat(result.getBundles()).isEmpty();
    }

    @Test
    void 인기_기준이면_점수_대신_상품의_평점과_리뷰_수를_내린다() throws IOException {
        RecommendationResultV2Response result = assemble("S2_SEARCH", RecommendationBasis.POPULAR,
                Map.of("11111111-1111-1111-1111-111111111111", product("11111111-1111-1111-1111-111111111111", 30000, "4.7", 2184)));

        Item first = result.getItems().get(0);
        assertThat(first.getTotalScore()).isNull();
        assertThat(first.getRating()).isEqualTo(4.7);
        assertThat(first.getReviewCount()).isEqualTo(2184);
        assertThat(result.getSummary().getBasisLabel()).isEqualTo("최근 30일 기준");
        // 상품 정보가 없으면 평점도 비운다
        assertThat(result.getItems().get(1).getRating()).isNull();
    }

    @Test
    void 상품_평가는_대체_상품의_유사도를_점수_분해에서_꺼낸다() throws IOException {
        RecommendationResultV2Response result = assemble("S1_EVALUATE", RecommendationBasis.SELF, Map.of());

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getAlternatives()).extracting(Alternative::getName, Alternative::getSimilarity, Alternative::getTotalScore)
                .containsExactly(tuple("글로우 쿠션", 88.0, 81), tuple("수분 쿠션", null, 77));
        // 상품 정보도 없으면 가격은 비운다
        assertThat(result.getAlternatives().get(1).getPrice()).isNull();
        assertThat(result.getSummary().getBasisLabel()).isEqualTo("지성 기준");
    }

    @Test
    void 예산_세트는_조합마다_합계_남은_예산_점수_합과_순서로_된_칸을_만든다() throws IOException {
        RecommendationResultV2Response result = assemble("S6_BUNDLE", RecommendationBasis.SELF,
                Map.of("55555555-5555-5555-5555-555555555555", product("55555555-5555-5555-5555-555555555555", 46000, null, null)));

        assertThat(result.getBundles()).hasSize(2);
        Bundle balanced = result.getBundles().get(0);
        assertThat(balanced.getIndex()).isEqualTo(1);
        assertThat(balanced.getType()).isNull();
        assertThat(balanced.getLabel()).isEqualTo("균형형");
        assertThat(balanced.getTotal()).isEqualTo(92000);
        assertThat(balanced.getRemaining()).isEqualTo(8000);
        assertThat(balanced.getTotalScore()).isEqualTo(225);
        assertThat(balanced.getSlots()).extracting(Slot::getSlotKey, Slot::getLabel, Slot::getName, Slot::getPrice, Slot::getScore)
                .containsExactly(
                        tuple("0", null, "그린티 토너", 22000, 80),
                        tuple("1", null, "비타 세럼", 38000, 75),
                        tuple("2", null, "수분 크림", 32000, 70));

        Bundle cheap = result.getBundles().get(1);
        assertThat(cheap.getIndex()).isEqualTo(2);
        assertThat(cheap.getRemaining()).isEqualTo(39000);
        assertThat(cheap.getSlots().get(1).getPrice()).isEqualTo(46000);

        assertThat(result.getSummary().getConditions()).containsExactly("토너", "세럼", "크림", "총 10만원");
        assertThat(result.getSummary().getNotice()).isEqualTo("가격 대비 효능과 후기를 함께 보고 골랐어요");
        assertThat(result.getSummary().getTotalCount()).isZero();
    }

    @Test
    void 조건_수정_결과는_순위_변화를_그대로_옮긴다() throws IOException {
        RecommendationResultV2Response result = assemble("S7_REFINE", RecommendationBasis.SELF, Map.of());

        assertThat(result.getItems()).extracting(Item::getChange, Item::getRankDelta)
                .containsExactly(tuple("NEW", null), tuple("UP", 3), tuple("DOWN", -1));
        assertThat(result.getSummary().getConditions()).containsExactly("매트", "쿠션", "2만원 이하");
    }

    @Test
    void 홈_환경_추천도_같은_모양으로_조립한다() throws IOException {
        RecommendationResultV2Response result = assemble("HOME_ENV", RecommendationBasis.SELF, Map.of());

        assertThat(result.getScenario()).isEqualTo("HOME_ENV");
        assertThat(result.getSummary().getCategoryLabel()).isEqualTo("선케어");
        assertThat(result.getSummary().getNotice()).isEqualTo("요즘 지내시는 곳의 날씨와 공기를 함께 반영했어요");
        assertThat(result.getItems().get(0).getBadges()).extracting("type", "text").containsExactly(tuple("ENV", "요즘 자외선이 강해요"));
    }

    @Test
    void 결과에_나오는_상품_ID를_한_번에_모은다() throws IOException {
        assertThat(ResultAssembler.productIdsOf(sample("S2_SEARCH"))).hasSize(3);
        assertThat(ResultAssembler.productIdsOf(sample("S6_BUNDLE"))).hasSize(5);
        // 상품 ID 형식이 아니면 빼고 모은다
        assertThat(ResultAssembler.productIdsOf(MAPPER.readTree("{\"items\":[{\"productId\":\"abc\"}]}"))).isEmpty();
    }

    @Test
    void 대체_후보를_뺀_수는_상태에_있으면_쓰고_없으면_0이다() throws IOException {
        assertThat(ResultAssembler.droppedCount(MAPPER.readTree("{\"alternativesDroppedCount\":2}"))).isEqualTo(2);
        assertThat(ResultAssembler.droppedCount(MAPPER.readTree("{\"alternatives_dropped_count\":1}"))).isEqualTo(1);
        assertThat(ResultAssembler.droppedCount(MissingNode.getInstance())).isZero();
    }

    @Test
    void 시나리오는_job_값을_먼저_쓰고_없으면_결과_값을_쓴다() throws IOException {
        Source source = new Source(JOB_ID, null, null, RecommendationBasis.SELF, sample("S1_EVALUATE"),
                MissingNode.getInstance(), null, MissingNode.getInstance());

        assertThat(ResultAssembler.assemble(source, Map.of(), null).getScenario()).isEqualTo("S1_EVALUATE");
    }
}
