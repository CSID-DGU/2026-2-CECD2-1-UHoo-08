package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.request.BundleSwapRequest;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse.Option;
import com.capstone.backend.domain.recommendation.dto.response.BundleSwapResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Bundle;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Slot;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
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
    void 칸의_후보가_비었거나_쓸_수_없는_후보뿐이면_NOT_FOUND다() {
        givenJob("100", "30", "");
        assertNotFound(1, "toner");

        givenJob("100", "30", "{\"productId\":\"a\",\"name\":\"가격 없음\",\"score\":90}");
        assertNotFound(1, "toner");
    }

    @Test
    void 후보가_지금_제품뿐이면_그_제품을_돌려준다() {
        givenJob("100", "30", candidate("cur", 30, 50));

        assertThat(service.getOptions(userId, jobId, 1, "toner").getOptions())
                .extracting(Option::getProductId, Option::isCurrent)
                .containsExactly(tuple("cur", true));
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

    // 세트 제품 교체

    private static final String GENTLE_TONER = "44444444-4444-4444-4444-444444444444";
    private static final String CUR = "aaaaaaaa-0000-0000-0000-000000000001";
    private static final String OTHER = "aaaaaaaa-0000-0000-0000-000000000002";

    private final ObjectMapper mapper = new ObjectMapper();

    private Recommendation givenLockedJob(JobStatus status, String result, String snapshot) {
        Recommendation job = Recommendation.builder().id(jobId).status(status).result(result).stateSnapshot(snapshot).build();
        given(recommendationRepository.findByIdAndUserIdForUpdate(jobId, userId)).willReturn(Optional.of(job));
        return job;
    }

    /** 합계 100, 지금 칸 가격 30 인 조합과 그 칸의 후보. 예산 초과 사유가 있다 */
    private Recommendation givenLockedJob(int budget, int otherPrice) {
        return givenLockedJob(JobStatus.COMPLETED,
                "{\"query\":{\"budgetTotal\":" + budget + "},\"bundles\":[{\"label\":\"균형형\",\"totalPrice\":100,"
                        + "\"overBudgetReason\":\"넘음\",\"items\":["
                        + "{\"productId\":\"" + CUR + "\",\"name\":\"지금 제품\",\"price\":30,\"totalScore\":50,\"slotKey\":\"toner\"},"
                        + "{\"productId\":\"etc\",\"name\":\"다른 칸\",\"price\":70,\"totalScore\":60,\"slotKey\":\"serum\"}]}]}",
                "{\"bundle_slots\":[{\"slotKey\":\"toner\",\"label\":\"토너\",\"candidates\":["
                        + candidate(OTHER, otherPrice, 90) + "]}]}");
    }

    private void givenProduct(String id) {
        given(productRepository.findById(UUID.fromString(id))).willReturn(Optional.of(
                Product.builder().id(UUID.fromString(id)).brand("새 브랜드").imageUrl("https://img/new").build()));
    }

    private static BundleSwapRequest swapRequest(String slotKey, String productId) {
        return BundleSwapRequest.builder().slotKey(slotKey).productId(productId).build();
    }

    private void assertSwapFails(int bundleIndex, BundleSwapRequest request, ErrorCode code) {
        assertThatThrownBy(() -> service.swap(userId, jobId, bundleIndex, request))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(code);
    }

    @Test
    void 칸을_바꾸면_갱신된_조합을_돌려주고_그_칸과_합계만_저장한다() throws IOException {
        Recommendation job = givenLockedJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));
        String snapshotBefore = job.getStateSnapshot();
        JsonNode before = mapper.readTree(job.getResult());
        givenProduct(GENTLE_TONER);

        BundleSwapResponse response = service.swap(userId, jobId, 1, swapRequest("toner", GENTLE_TONER));

        Bundle bundle = response.getBundle();
        assertThat(bundle.getIndex()).isEqualTo(1);
        assertThat(bundle.getTotal()).isEqualTo(85000);
        assertThat(bundle.getRemaining()).isEqualTo(15000);
        assertThat(bundle.getTotalScore()).isEqualTo(217);
        assertThat(bundle.getSlots()).extracting(Slot::getSlotKey, Slot::getLabel, Slot::getProductId, Slot::getName, Slot::getPrice, Slot::getScore)
                .containsExactly(
                        tuple("toner", "토너", GENTLE_TONER, "순한 토너", 15000, 72),
                        tuple("serum", "세럼", "22222222-2222-2222-2222-222222222222", "비타 세럼", 38000, 75),
                        tuple("cream", "크림", "33333333-3333-3333-3333-333333333333", "수분 크림", 32000, 70));

        JsonNode saved = mapper.readTree(job.getResult());
        JsonNode item = saved.path("bundles").get(0).path("items").get(0);
        assertThat(saved.path("bundles").get(0).path("totalPrice").asInt()).isEqualTo(85000);
        assertThat(item.path("brand").asText()).isEqualTo("새 브랜드");
        assertThat(item.path("imageUrl").asText()).isEqualTo("https://img/new");
        assertThat(item.path("slotKey").asText()).isEqualTo("toner");
        assertThat(saved.path("bundles").get(1)).isEqualTo(before.path("bundles").get(1));
        assertThat(saved.path("bundles").get(0).path("items").get(1)).isEqualTo(before.path("bundles").get(0).path("items").get(1));
        assertThat(saved.path("query")).isEqualTo(before.path("query"));
        assertThat(job.getStateSnapshot()).isEqualTo(snapshotBefore);
        assertThat(job.getUpdatedAt()).isNotNull();
    }

    @Test
    void 바꾼_뒤_다시_조회하면_바뀐_제품이_지금_제품이다() throws IOException {
        Recommendation job = givenLockedJob(JobStatus.COMPLETED, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));
        givenProduct(GENTLE_TONER);
        service.swap(userId, jobId, 1, swapRequest("toner", GENTLE_TONER));
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(job));

        BundleSlotOptionsResponse options = service.getOptions(userId, jobId, 1, "toner");

        assertThat(options.getCurrentTotal()).isEqualTo(85000);
        assertThat(options.getOptions()).extracting(Option::getName, Option::getNewTotal, Option::isCurrent)
                .containsExactly(tuple("그린티 토너", 92000, false), tuple("순한 토너", 85000, true));
    }

    @Test
    void 이전_제품의_점수_분해와_배지와_이유를_지운다() throws IOException {
        Recommendation job = givenLockedJob(100, 30);
        ObjectNode result = (ObjectNode) mapper.readTree(job.getResult());
        ObjectNode item = (ObjectNode) result.path("bundles").get(0).path("items").get(0);
        item.putArray("breakdown").add("이전");
        item.putArray("badges").add("이전");
        item.put("reason", "이전");
        job.replaceResult(result.toString(), null);
        givenProduct(OTHER);

        service.swap(userId, jobId, 1, swapRequest("toner", OTHER));

        JsonNode saved = mapper.readTree(job.getResult()).path("bundles").get(0).path("items").get(0);
        assertThat(saved.path("breakdown")).isEmpty();
        assertThat(saved.path("badges")).isEmpty();
        assertThat(saved.path("reason").isNull()).isTrue();
    }

    @Test
    void 정확히_0이_남으면_바꾸고_예산_초과_사유를_지운다() throws IOException {
        Recommendation job = givenLockedJob(100, 30);
        givenProduct(OTHER);

        assertThat(service.swap(userId, jobId, 1, swapRequest("toner", OTHER)).getBundle().getRemaining()).isZero();

        assertThat(mapper.readTree(job.getResult()).path("bundles").get(0).path("overBudgetReason").isNull()).isTrue();
    }

    @Test
    void 일원이라도_넘으면_BUNDLE_OVER_BUDGET이고_저장하지_않는다() {
        Recommendation job = givenLockedJob(100, 31);
        String before = job.getResult();

        assertSwapFails(1, swapRequest("toner", OTHER), ErrorCode.BUNDLE_OVER_BUDGET);

        assertThat(job.getResult()).isEqualTo(before);
    }

    @Test
    void 지금_제품을_다시_고르면_저장하지_않고_지금_조합을_돌려준다() {
        Recommendation job = givenLockedJob(100, 30);
        String before = job.getResult();

        BundleSwapResponse response = service.swap(userId, jobId, 1, swapRequest("toner", CUR));

        assertThat(response.getBundle().getTotal()).isEqualTo(100);
        assertThat(job.getResult()).isEqualTo(before);
        assertThat(job.getUpdatedAt()).isNull();
    }

    @Test
    void 후보에_없는_제품이면_NOT_FOUND이고_저장하지_않는다() {
        Recommendation job = givenLockedJob(100, 30);
        String before = job.getResult();

        assertSwapFails(1, swapRequest("toner", UUID.randomUUID().toString()), ErrorCode.NOT_FOUND);

        assertThat(job.getResult()).isEqualTo(before);
    }

    @Test
    void 교체에서_없는_조합이나_칸이면_NOT_FOUND다() {
        givenLockedJob(100, 30);

        assertSwapFails(9, swapRequest("toner", OTHER), ErrorCode.NOT_FOUND);
        assertSwapFails(1, swapRequest("serum", OTHER), ErrorCode.NOT_FOUND);
    }

    @Test
    void 교체에서_없는_job이나_완료되지_않은_job이면_NOT_FOUND다() throws IOException {
        given(recommendationRepository.findByIdAndUserIdForUpdate(jobId, userId)).willReturn(Optional.empty());
        assertSwapFails(1, swapRequest("toner", OTHER), ErrorCode.NOT_FOUND);

        givenLockedJob(JobStatus.IN_PROGRESS, sample("S6_BUNDLE"), sample("S6_BUNDLE_SNAPSHOT"));
        assertSwapFails(1, swapRequest("toner", GENTLE_TONER), ErrorCode.NOT_FOUND);
    }

    @Test
    void 상품_정보가_없는_후보면_NOT_FOUND이고_저장하지_않는다() {
        Recommendation job = givenLockedJob(100, 30);
        String before = job.getResult();
        given(productRepository.findById(UUID.fromString(OTHER))).willReturn(Optional.empty());

        assertSwapFails(1, swapRequest("toner", OTHER), ErrorCode.NOT_FOUND);

        assertThat(job.getResult()).isEqualTo(before);
    }
}
