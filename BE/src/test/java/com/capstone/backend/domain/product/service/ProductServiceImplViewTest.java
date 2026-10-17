package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.ProductViewRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Pageable;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ProductServiceImplViewTest {

    @Mock
    ProductRepository productRepository;
    @Mock
    ProductViewRepository productViewRepository;
    @InjectMocks
    ProductServiceImpl productService;

    private final UUID userId = UUID.randomUUID();

    private Product product(UUID id, String name) {
        return Product.builder().id(id).name(name).brand("브랜드").category("토너").build();
    }

    @Test
    void 조회는_product_views에_upsert로_남긴다() {
        UUID productId = UUID.randomUUID();

        productService.recordView(userId, productId);

        verify(productViewRepository).upsertView(userId, productId);
    }

    @Test
    void 최근_본_상품은_마지막으로_본_순서를_지킨다() {
        UUID first = UUID.randomUUID();
        UUID second = UUID.randomUUID();
        given(productViewRepository.findRecentProductIds(eq(userId), argThat((Pageable p) -> p.getPageSize() == 5)))
                .willReturn(List.of(second, first));
        // DB 는 순서를 보장하지 않고 돌려준다
        given(productRepository.findAllById(List.of(second, first)))
                .willReturn(List.of(product(first, "첫째"), product(second, "둘째")));

        ProductSearchResponse response = productService.getRecentlyViewed(userId, 5);

        assertThat(response.getProducts()).extracting(ProductSearchResponse.ProductItem::getId)
                .containsExactly(second, first);
    }

    @Test
    void 본_상품이_없으면_제품을_조회하지_않는다() {
        given(productViewRepository.findRecentProductIds(eq(userId), any())).willReturn(List.of());

        ProductSearchResponse response = productService.getRecentlyViewed(userId, 10);

        assertThat(response.getProducts()).isEmpty();
        verify(productRepository, never()).findAllById(any());
    }

    @Test
    void 지워진_제품은_최근_본_상품에서_빠진다() {
        UUID kept = UUID.randomUUID();
        UUID deleted = UUID.randomUUID();
        given(productViewRepository.findRecentProductIds(eq(userId), any())).willReturn(List.of(deleted, kept));
        given(productRepository.findAllById(List.of(deleted, kept))).willReturn(List.of(product(kept, "남은 제품")));

        ProductSearchResponse response = productService.getRecentlyViewed(userId, 10);

        assertThat(response.getProducts()).extracting(ProductSearchResponse.ProductItem::getId).containsExactly(kept);
    }
}
