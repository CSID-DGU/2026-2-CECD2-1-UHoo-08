package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityCheckResponse;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityPairDetail;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse.Pair;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse.Conflict;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class CompatibilityServiceTest {

    @Mock
    UserProductRepository userProductRepository;
    @Mock
    ProductRepository productRepository;
    @Mock
    AiInternalClient aiInternalClient;
    @InjectMocks
    CompatibilityService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();

    private final List<UserProduct> rows = new ArrayList<>();
    private final List<Product> products = new ArrayList<>();

    private UserProduct using(String name) {
        Product product = Product.builder().id(UUID.randomUUID()).name(name).build();
        UserProduct row = UserProduct.builder().id(UUID.randomUUID()).userId(userId).productId(product.getId())
                .usageType(UsageType.USING).build();
        products.add(product);
        rows.add(row);
        return row;
    }

    private void givenHoldings() {
        given(productRepository.existsById(productId)).willReturn(true);
        given(userProductRepository.findByUserIdAndUsageTypeIn(userId, List.of(UsageType.USING))).willReturn(rows);
        lenient().when(productRepository.findAllById(any())).thenReturn(products);
    }

    private void givenAi(CompatibilityLevel level, CompatibilityPairDetail... pairs) {
        given(aiInternalClient.checkCompatibility(userId, productId))
                .willReturn(new CompatibilityCheckResponse(level, List.of(pairs), false));
    }

    private static CompatibilityPairDetail pair(UserProduct row, String a, String b, CompatibilityLevel level,
                                                String advice, String schedule) {
        return new CompatibilityPairDetail(row.getId().toString(), a, b, level, advice, schedule);
    }

    @Test
    void 시간을_나눠_쓸_쌍은_주의_문구와_쌍을_내려보낸다() {
        UserProduct retinol = using("레티놀 앰플");
        givenHoldings();
        givenAi(CompatibilityLevel.SEPARATE,
                pair(retinol, "AHA", "레티놀", CompatibilityLevel.SEPARATE, "저녁에 나눠 쓰세요", "AHA는 아침, 레티놀은 저녁"));

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.SEPARATE);
        assertThat(response.getBannerText()).isEqualTo("지금 쓰시는 제품 1개와 시간대를 나눠 쓰세요");
        assertThat(response.getBasis()).hasSize(3);
        Pair pair = response.getPairs().get(0);
        assertThat(pair.getUserProductId()).isEqualTo(retinol.getId());
        assertThat(pair.getUserProductName()).isEqualTo("레티놀 앰플");
        assertThat(pair.getIngredientA()).isEqualTo("AHA");
        assertThat(pair.getIngredientB()).isEqualTo("레티놀");
        assertThat(pair.getTitle()).isEqualTo("AHA와 레티놀은 시간대를 나눠 쓰세요");
        assertThat(pair.getReason()).isEqualTo("저녁에 나눠 쓰세요");
        assertThat(pair.getSchedule().getMorning()).isNull();
        assertThat(pair.getSchedule().getEvening()).isNull();
        assertThat(pair.getSchedule().getTip()).isEqualTo("AHA는 아침, 레티놀은 저녁");
    }

    @Test
    void 같이_쓰면_안_되는_쌍이_있으면_가장_심한_단계로_정하고_앞에_둔다() {
        UserProduct retinol = using("레티놀 앰플");
        UserProduct toner = using("AHA 토너");
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID,
                pair(toner, "비타민C", "AHA", CompatibilityLevel.SEPARATE, null, null),
                pair(retinol, "비타민C", "레티놀", CompatibilityLevel.AVOID, null, null));

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.AVOID);
        assertThat(response.getBannerText()).isEqualTo("지금 쓰시는 제품 1개와 같이 쓰면 안 돼요");
        assertThat(response.getPairs()).extracting(Pair::getUserProductName).containsExactly("레티놀 앰플", "AHA 토너");
        assertThat(response.getPairs().get(0).getTitle()).isEqualTo("비타민C와 레티놀은 같이 쓰지 마세요");
    }

    @Test
    void 문구의_제품_수는_쌍이_아니라_보유_제품을_센다() {
        UserProduct retinol = using("레티놀 앰플");
        UserProduct serum = using("펩타이드 세럼");
        givenHoldings();
        givenAi(CompatibilityLevel.SEPARATE,
                pair(retinol, "AHA", "레티놀", CompatibilityLevel.SEPARATE, null, null),
                pair(retinol, "BHA", "레티놀", CompatibilityLevel.SEPARATE, null, null),
                pair(serum, "AHA", "펩타이드", CompatibilityLevel.SEPARATE, null, null));

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getPairs()).hasSize(3);
        assertThat(response.getBannerText()).isEqualTo("지금 쓰시는 제품 2개와 시간대를 나눠 쓰세요");
    }

    @Test
    void 충돌이_없으면_문구가_없다() {
        using("수분 크림");
        givenHoldings();
        givenAi(CompatibilityLevel.OK);

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.OK);
        assertThat(response.getBannerText()).isNull();
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getBasis()).hasSize(3);
    }

    @Test
    void 쓰는_제품이_없으면_AI를_부르지_않고_OK다() {
        givenHoldings();

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.OK);
        verify(aiInternalClient, never()).checkCompatibility(any(), any());
    }

    @Test
    void 이_제품만_쓰고_있으면_AI를_부르지_않고_OK다() {
        rows.add(UserProduct.builder().id(UUID.randomUUID()).userId(userId).productId(productId)
                .usageType(UsageType.USING).build());
        givenHoldings();

        assertThat(service.check(userId, productId).getLevel()).isEqualTo(CompatibilityLevel.OK);
        verify(aiInternalClient, never()).checkCompatibility(any(), any());
    }

    @Test
    void 없는_상품이면_PRODUCT_NOT_FOUND다() {
        given(productRepository.existsById(productId)).willReturn(false);

        assertThatThrownBy(() -> service.check(userId, productId))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.PRODUCT_NOT_FOUND);
    }

    @Test
    void 지금_쓰지_않는_제품의_쌍을_빼면_판정도_다시_정한다() {
        using("수분 크림");
        UserProduct finished = UserProduct.builder().id(UUID.randomUUID()).build();
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID, pair(finished, "AHA", "레티놀", CompatibilityLevel.AVOID, null, null));

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.OK);
        assertThat(response.getBannerText()).isNull();
        assertThat(response.getPairs()).isEmpty();
    }

    @Test
    void 이_제품_자신과의_쌍은_뺀다() {
        UserProduct self = UserProduct.builder().id(UUID.randomUUID()).userId(userId).productId(productId)
                .usageType(UsageType.USING).build();
        rows.add(self);
        using("수분 크림");
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID, pair(self, "AHA", "레티놀", CompatibilityLevel.AVOID, null, null));

        assertThat(service.check(userId, productId).getPairs()).isEmpty();
    }

    @Test
    void 괜찮은_쌍과_판정_단계가_없는_쌍은_뺀다() {
        UserProduct cream = using("수분 크림");
        givenHoldings();
        givenAi(CompatibilityLevel.OK,
                pair(cream, "AHA", "세라마이드", CompatibilityLevel.OK, null, null),
                pair(cream, "AHA", "판테놀", null, null, null));

        assertThat(service.check(userId, productId).getPairs()).isEmpty();
    }

    @Test
    void 비어_있거나_성분_이름이_없는_쌍은_빼고_나머지로_판정한다() {
        UserProduct cream = using("수분 크림");
        givenHoldings();
        given(aiInternalClient.checkCompatibility(userId, productId))
                .willReturn(new CompatibilityCheckResponse(CompatibilityLevel.AVOID, Arrays.asList(
                        null,
                        pair(cream, null, "레티놀", CompatibilityLevel.AVOID, null, null),
                        pair(cream, "레티놀", null, CompatibilityLevel.AVOID, null, null),
                        pair(cream, "AHA", "레티놀", CompatibilityLevel.SEPARATE, null, null)), false));

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.SEPARATE);
        assertThat(response.getPairs()).extracting(Pair::getIngredientA).containsExactly("AHA");
    }

    @Test
    void 이름을_모르는_보유_제품의_쌍은_뺀다() {
        UserProduct cream = using("수분 크림");
        products.clear();
        givenHoldings();
        givenAi(CompatibilityLevel.SEPARATE, pair(cream, "AHA", "레티놀", CompatibilityLevel.SEPARATE, null, null));

        assertThat(service.check(userId, productId).getPairs()).isEmpty();
    }

    @Test
    void 설명이_없으면_단계별_기본_문장을_쓰고_시간대_안내는_null이다() {
        UserProduct retinol = using("레티놀 앰플");
        UserProduct toner = using("AHA 토너");
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID,
                pair(retinol, "AHA", "레티놀", CompatibilityLevel.AVOID, " ", " "),
                pair(toner, "AHA", "BHA", CompatibilityLevel.SEPARATE, null, null));

        List<Pair> pairs = service.check(userId, productId).getPairs();

        assertThat(pairs.get(0).getReason()).isEqualTo("성분 조합상 같이 쓰지 않는 것이 좋아요");
        assertThat(pairs.get(0).getSchedule()).isNull();
        assertThat(pairs.get(1).getReason()).isEqualTo("성분 조합상 시간대를 나눠 쓰는 것이 좋아요");
        assertThat(pairs.get(1).getSchedule()).isNull();
    }

    @Test
    void AI가_실패해_돌려준_기본값이면_OK다() {
        using("수분 크림");
        givenHoldings();
        given(aiInternalClient.checkCompatibility(userId, productId)).willReturn(CompatibilityCheckResponse.ok());

        ProductCompatibilityResponse response = service.check(userId, productId);

        assertThat(response.getLevel()).isEqualTo(CompatibilityLevel.OK);
        assertThat(response.getBannerText()).isNull();
    }

    @Test
    void 등록_충돌_목록은_보유_제품당_가장_심한_쌍_하나다() {
        UserProduct retinol = using("레티놀 앰플");
        UserProduct toner = using("AHA 토너");
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID,
                pair(retinol, "AHA", "레티놀", CompatibilityLevel.SEPARATE, "나눠 쓰세요", null),
                pair(toner, "AHA", "BHA", CompatibilityLevel.SEPARATE, "시간을 두세요", null),
                pair(retinol, "비타민C", "레티놀", CompatibilityLevel.AVOID, "같이 쓰지 마세요", null));

        List<Conflict> conflicts = service.conflictsOf(userId, productId);

        assertThat(conflicts).extracting(Conflict::getUserProductId, Conflict::getName, Conflict::getLevel, Conflict::getAdvice)
                .containsExactly(
                        tuple(retinol.getId(), "레티놀 앰플", "AVOID", "같이 쓰지 마세요"),
                        tuple(toner.getId(), "AHA 토너", "SEPARATE", "시간을 두세요"));
    }

    @Test
    void 등록한_제품과_같은_행은_충돌_상대에서_뺀다() {
        UserProduct registered = UserProduct.builder().id(UUID.randomUUID()).userId(userId).productId(productId)
                .usageType(UsageType.USING).build();
        rows.add(registered);
        UserProduct cream = using("수분 크림");
        givenHoldings();
        givenAi(CompatibilityLevel.AVOID,
                pair(registered, "AHA", "AHA", CompatibilityLevel.AVOID, null, null),
                pair(cream, "AHA", "레티놀", CompatibilityLevel.SEPARATE, null, null));

        assertThat(service.conflictsOf(userId, productId)).extracting(Conflict::getUserProductId)
                .containsExactly(cream.getId());
    }

    @Test
    void 등록_충돌_목록은_충돌이_없으면_비어_있다() {
        using("수분 크림");
        givenHoldings();
        given(aiInternalClient.checkCompatibility(userId, productId)).willReturn(CompatibilityCheckResponse.ok());

        assertThat(service.conflictsOf(userId, productId)).isEmpty();
    }

    @Test
    void 등록_충돌_목록은_확인이_실패해도_예외를_올리지_않는다() {
        given(productRepository.existsById(productId)).willThrow(new IllegalStateException("DB 연결 실패"));

        assertThat(service.conflictsOf(userId, productId)).isEmpty();
    }

    @Test
    void AI가_stub이면_OK다() {
        using("수분 크림");
        givenHoldings();
        given(aiInternalClient.checkCompatibility(userId, productId))
                .willReturn(new CompatibilityCheckResponse(CompatibilityLevel.OK, List.of(), true));

        assertThat(service.check(userId, productId).getLevel()).isEqualTo(CompatibilityLevel.OK);
    }
}
