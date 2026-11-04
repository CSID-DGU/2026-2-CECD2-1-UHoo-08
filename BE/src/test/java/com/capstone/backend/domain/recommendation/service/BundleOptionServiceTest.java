package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse.Option;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.lenient;

@ExtendWith(MockitoExtension.class)
class BundleOptionServiceTest {

    private static final String AMPOULE = "55555555-5555-5555-5555-555555555555";

    @Mock
    RecommendationRepository recommendationRepository;
    @Mock
    ProductRepository productRepository;

    BundleOptionService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new BundleOptionService(recommendationRepository, productRepository, new JsonUtil(new ObjectMapper()));
        lenient().when(productRepository.findAllById(any())).thenReturn(List.of());
    }

    private static String sample(String name) throws IOException {
        try (InputStream in = BundleOptionServiceTest.class.getResourceAsStream("/ai-results/" + name + ".json")) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private void givenJob(JobStatus status, String result, String snapshot) {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(
                Recommendation.builder().id(jobId).status(status).result(result).stateSnapshot(snapshot).build()));
    }

    /** 합계 100, 지금 칸 가격 30 인 조합과 그 칸의 후보 */
    private void givenJob(String budget, String currentPrice, String candidates) {
        givenJob(JobStatus.COMPLETED,
                "{\"query\":{\"budgetTotal\":" + budget + "},\"bundles\":[{\"label\":\"균형형\",\"totalPrice\":100,\"items\":["
                        + "{\"productId\":\"cur\",\"name\":\"지금 제품\",\"price\":" + currentPrice + ",\"totalScore\":50,\"slotKey\":\"toner\"},"
                        + "{\"productId\":\"etc\",\"name\":\"다른 칸\",\"price\":70,\"totalScore\":60,\"slotKey\":\"serum\"}]}]}",
                "{\"bundle_slots\":[{\"slotKey\":\"toner\",\"label\":\"토너\",\"candidates\":[" + candidates + "]}]}");
    }

    private static String candidate(String id, int price, Integer score) {
        return "{\"productId\":\"" + id + "\",\"name\":\"" + id + "\",\"price\":" + price + ",\"score\":" + score + "}";
    }

    private Option optionOf(BundleSlotOptionsResponse response, String productId) {
        return response.getOptions().stream().filter(o -> o.getProductId().equals(productId)).findFirst().orElseThrow();
    }

    private void assertNotFound(int bundleIndex, String slotKey) {
        assertThatThrownBy(() -> service.getOptions(userId, jobId, bundleIndex, slotKey))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.NOT_FOUND);
    }

    @Test
    void 샘플_결과로_후보마다_바꿨을_때의_총액을_적합도순으로_돌려준다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 1, "toner");

        assertThat(response.getBudget()).isEqualTo(100000);
        assertThat(response.getCurrentTotal()).isEqualTo(92000);
        assertThat(response.getOptions())
                .extracting(Option::getName, Option::getPrice, Option::getScore, Option::getNewTotal, Option::getRemaining,
                        Option::isCurrent, Option::isSelectable, Option::getOverBudgetBy)
                .containsExactly(
                        tuple("그린티 토너", 22000, 80, 92000, 8000, true, true, null),
                        tuple("순한 토너", 15000, 72, 85000, 15000, false, true, null));
    }

    @Test
    void 조합_번호로_그_조합의_합계와_지금_제품을_쓴다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 2, "toner");

        assertThat(response.getCurrentTotal()).isEqualTo(61000);
        assertThat(response.getOptions()).extracting(Option::getName, Option::getNewTotal, Option::isCurrent)
                .containsExactly(tuple("그린티 토너", 68000, false), tuple("순한 토너", 61000, true));
    }

    @Test
    void 정확히_0이_남으면_선택할_수_있다() {
        givenJob("100", "30", candidate("a", 30, 90));

        Option option = optionOf(service.getOptions(userId, jobId, 1, "toner"), "a");

        assertThat(option.getNewTotal()).isEqualTo(100);
        assertThat(option.getRemaining()).isZero();
        assertThat(option.isSelectable()).isTrue();
        assertThat(option.getOverBudgetBy()).isNull();
    }

    @Test
    void 일원이라도_넘으면_선택할_수_없고_초과_금액을_알려_준다() {
        givenJob("100", "30", candidate("a", 31, 90));

        Option option = optionOf(service.getOptions(userId, jobId, 1, "toner"), "a");

        assertThat(option.getNewTotal()).isEqualTo(101);
        assertThat(option.getRemaining()).isEqualTo(-1);
        assertThat(option.isSelectable()).isFalse();
        assertThat(option.getOverBudgetBy()).isEqualTo(1);
    }

    @Test
    void 지금_제품이_후보에_없으면_목록에_넣고_적합도순으로_둔다() {
        givenJob("100", "30", candidate("a", 20, 90) + "," + candidate("b", 20, 40));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 1, "toner");

        assertThat(response.getOptions()).extracting(Option::getProductId, Option::getScore, Option::isCurrent)
                .containsExactly(tuple("a", 90, false), tuple("cur", 50, true), tuple("b", 40, false));
        Option current = optionOf(response, "cur");
        assertThat(current.getName()).isEqualTo("지금 제품");
        assertThat(current.getNewTotal()).isEqualTo(100);
    }

    @Test
    void 지금_제품은_후보의_가격이_달라도_합계가_그대로다() {
        givenJob("100", "30", candidate("cur", 99, 70));

        Option current = optionOf(service.getOptions(userId, jobId, 1, "toner"), "cur");

        assertThat(current.getPrice()).isEqualTo(30);
        assertThat(current.getScore()).isEqualTo(70);
        assertThat(current.getNewTotal()).isEqualTo(100);
    }

    @Test
    void 점수가_없는_후보는_빼고_지금_제품은_칸의_점수로_남긴다() {
        givenJob("100", "30", candidate("a", 20, null) + "," + candidate("cur", 30, null));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 1, "toner");

        assertThat(response.getOptions()).extracting(Option::getProductId, Option::getScore)
                .containsExactly(tuple("cur", 50));
    }

    @Test
    void 예산이_없으면_모두_선택할_수_있고_남는_예산이_null이다() {
        givenJob("null", "30", candidate("a", 1000, 90));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 1, "toner");

        assertThat(response.getBudget()).isNull();
        Option option = optionOf(response, "a");
        assertThat(option.getNewTotal()).isEqualTo(1070);
        assertThat(option.getRemaining()).isNull();
        assertThat(option.isSelectable()).isTrue();
        assertThat(option.getOverBudgetBy()).isNull();
    }

    @Test
    void 칸_가격을_모르면_0으로_계산한다() {
        givenJob("200", "null", candidate("a", 20, 90));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 1, "toner");

        assertThat(optionOf(response, "a").getNewTotal()).isEqualTo(120);
        assertThat(optionOf(response, "cur").getPrice()).isZero();
        assertThat(optionOf(response, "cur").getNewTotal()).isEqualTo(100);
    }

    @Test
    void AI가_가격을_비워_둔_칸은_결과_조회처럼_상품의_정가로_계산한다() throws IOException {
        given(productRepository.findAllById(any())).willReturn(List.of(
                Product.builder().id(UUID.fromString(AMPOULE)).originalPrice(46000).build()));
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        BundleSlotOptionsResponse response = service.getOptions(userId, jobId, 2, "serum");

        // 합계 61000 에서 앰플 정가 46000 을 빼고 비타 세럼 38000 을 더한다
        assertThat(optionOf(response, "22222222-2222-2222-2222-222222222222").getNewTotal()).isEqualTo(53000);
    }

    @Test
    void 없는_job이나_다른_사람의_job이면_NOT_FOUND다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.empty());

        assertNotFound(1, "toner");
    }

    @Test
    void 완료되지_않은_job이면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.IN_PROGRESS, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        assertNotFound(1, "toner");
    }

    @Test
    void 없는_조합이면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        assertNotFound(0, "toner");
        assertNotFound(3, "toner");
    }

    @Test
    void 조합에_없는_칸이면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        assertNotFound(1, "sunscreen");
    }

    @Test
    void 칸별_후보에_없는_칸이면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));

        assertNotFound(1, "cream");
    }

    @Test
    void 칸별_후보가_없는_기존_결과면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), "{}");

        assertNotFound(1, "toner");
    }

    @Test
    void 결과가_깨졌으면_NOT_FOUND다() {
        givenJob(JobStatus.COMPLETED, "{깨짐", "{}");

        assertNotFound(1, "toner");
    }

    @Test
    void 세트가_아닌_결과면_NOT_FOUND다() throws IOException {
        givenJob(JobStatus.COMPLETED, sample("S2_SEARCH"), "{}");

        assertNotFound(1, "toner");
    }
}
