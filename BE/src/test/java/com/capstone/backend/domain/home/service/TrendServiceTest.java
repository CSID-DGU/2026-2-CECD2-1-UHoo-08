package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse.Item;
import com.capstone.backend.domain.home.repository.ProductTrendDailyRepository;
import com.capstone.backend.domain.home.repository.TrendScoreSum;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class TrendServiceTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 9, 20);
    private static final LocalDate RECENT_FROM = LocalDate.of(2026, 8, 22);
    private static final LocalDate PREVIOUS_FROM = LocalDate.of(2026, 7, 23);
    private static final LocalDate PREVIOUS_TO = LocalDate.of(2026, 8, 21);
    private static final OffsetDateTime UPDATED = OffsetDateTime.of(2026, 9, 20, 4, 0, 0, 0, ZoneOffset.UTC);

    @Mock
    ProductTrendDailyRepository productTrendDailyRepository;
    @Mock
    ProductRepository productRepository;

    TrendService service;

    private final UUID cushion = UUID.randomUUID();
    private final UUID tint = UUID.randomUUID();
    private final UUID deleted = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new TrendService(productTrendDailyRepository, productRepository, new HwadamProperties());
    }

    @Test
    void 최근_30일_지수_합_순으로_순위를_매기고_직전_30일과_비교해_증가율을_낸다() {
        given(productTrendDailyRepository.findTopScoreSums(RECENT_FROM, TODAY, PageRequest.of(0, 10)))
                .willReturn(List.of(new TrendScoreSum(cushion, 138.0), new TrendScoreSum(tint, 50.0)));
        given(productTrendDailyRepository.findScoreSums(List.of(cushion, tint), PREVIOUS_FROM, PREVIOUS_TO))
                .willReturn(List.of(new TrendScoreSum(cushion, 100.0)));
        given(productRepository.findAllById(List.of(cushion, tint))).willReturn(List.of(
                Product.builder().id(tint).name("쥬시 래스팅 틴트").brand("ROMAND").originalPrice(13000).build(),
                Product.builder().id(cushion).name("베어 워터 쿠션").brand("ROMAND").lowestPrice(28000)
                        .originalPrice(32000).imageUrl("https://img/cushion.png").build()));
        given(productTrendDailyRepository.findLatestUpdatedAt(RECENT_FROM, TODAY)).willReturn(UPDATED);

        TrendProductsResponse response = service.getProducts(10, TODAY);

        assertThat(response.getPeriodDays()).isEqualTo(30);
        assertThat(response.getItems())
                .extracting(Item::getRank, Item::getName, Item::getPrice, Item::getImageUrl, Item::getInterestChangePct)
                .containsExactly(
                        tuple(1, "베어 워터 쿠션", 28000, "https://img/cushion.png", 38),
                        tuple(2, "쥬시 래스팅 틴트", 13000, null, null));
        assertThat(response.getUpdatedAt()).isEqualTo(UPDATED);
    }

    @Test
    void 지워진_상품은_순위에서_빼고_다음_순위를_당긴다() {
        given(productTrendDailyRepository.findTopScoreSums(RECENT_FROM, TODAY, PageRequest.of(0, 3)))
                .willReturn(List.of(new TrendScoreSum(deleted, 90.0), new TrendScoreSum(cushion, 80.0)));
        given(productTrendDailyRepository.findScoreSums(anyList(), eq(PREVIOUS_FROM),
                eq(PREVIOUS_TO))).willReturn(List.of());
        given(productRepository.findAllById(List.of(deleted, cushion))).willReturn(List.of(
                Product.builder().id(cushion).name("베어 워터 쿠션").brand("ROMAND").build()));

        TrendProductsResponse response = service.getProducts(3, TODAY);

        assertThat(response.getItems()).extracting(Item::getRank, Item::getProductId).containsExactly(tuple(1, cushion));
    }

    @Test
    void 기록이_없으면_빈_목록이고_상품을_찾지_않는다() {
        given(productTrendDailyRepository.findTopScoreSums(RECENT_FROM, TODAY, PageRequest.of(0, 10))).willReturn(List.of());

        TrendProductsResponse response = service.getProducts(10, TODAY);

        assertThat(response.getItems()).isEmpty();
        assertThat(response.getUpdatedAt()).isNull();
        verifyNoInteractions(productRepository);
        verify(productTrendDailyRepository).findLatestUpdatedAt(RECENT_FROM, TODAY);
    }

    @Test
    void 증가율은_직전_합이_없거나_0이면_null이고_줄었으면_음수다() {
        assertThat(TrendService.changePercent(138.0, 100.0)).isEqualTo(38);
        assertThat(TrendService.changePercent(50.0, 100.0)).isEqualTo(-50);
        assertThat(TrendService.changePercent(10.0, 0.0)).isNull();
        assertThat(TrendService.changePercent(10.0, null)).isNull();
    }

    @Test
    void 개수가_1에서_20_밖이면_VALIDATION_ERROR다() {
        for (int limit : new int[]{0, 21}) {
            assertThatThrownBy(() -> service.getProducts(limit, TODAY))
                    .isInstanceOf(BusinessException.class)
                    .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        }
        verifyNoInteractions(productTrendDailyRepository, productRepository);
    }
}
