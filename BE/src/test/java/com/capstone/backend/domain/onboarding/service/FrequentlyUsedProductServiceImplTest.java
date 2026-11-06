package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;
import com.capstone.backend.domain.onboarding.entity.FrequentlyUsedProduct;
import com.capstone.backend.domain.onboarding.repository.FrequentlyUsedProductRepository;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 온보딩의 "자주 사용하는 제품"은 frequently_used_products 에만 남는다.
 * 서비스가 사용 기록(UserProductRepository)을 아예 의존하지 않으므로, 사용 기록을 건드릴 길이 없다.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class FrequentlyUsedProductServiceImplTest {

    @Mock
    ProductRepository productRepository;
    @Mock
    FrequentlyUsedProductRepository frequentlyUsedProductRepository;
    @Mock
    UserRepository userRepository;
    @InjectMocks
    FrequentlyUsedProductServiceImpl service;

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();
    private User user;
    private Product product;

    @BeforeEach
    void setUp() {
        user = User.builder().id(userId).name("하림").provider("KAKAO").build();
        product = Product.builder().id(productId).name("독도 토너").brand("라운드랩").category("토너").build();
        given(userRepository.findById(userId)).willReturn(Optional.of(user));
        given(productRepository.findById(productId)).willReturn(Optional.of(product));
    }

    private FrequentlyUsedProductBatchRequest batch(UUID... ids) {
        FrequentlyUsedProductBatchRequest request = new FrequentlyUsedProductBatchRequest();
        ReflectionTestUtils.setField(request, "productIds", List.of(ids));
        return request;
    }

    @Test
    void 고른_제품을_frequently_used_products에_남긴다() {
        given(frequentlyUsedProductRepository.existsByUserIdAndProductId(userId, productId)).willReturn(false);

        int saved = service.saveBatch(userId, batch(productId));

        assertThat(saved).isEqualTo(1);
        ArgumentCaptor<FrequentlyUsedProduct> captor = ArgumentCaptor.forClass(FrequentlyUsedProduct.class);
        verify(frequentlyUsedProductRepository).save(captor.capture());
        assertThat(captor.getValue().getUser()).isEqualTo(user);
        assertThat(captor.getValue().getProduct()).isEqualTo(product);
    }

    @Test
    void 이미_고른_제품은_다시_넣지_않는다() {
        // 온보딩 화면은 다시 들어와 완료할 수 있다
        given(frequentlyUsedProductRepository.existsByUserIdAndProductId(userId, productId)).willReturn(true);

        int saved = service.saveBatch(userId, batch(productId));

        assertThat(saved).isZero();
        verify(frequentlyUsedProductRepository, never()).save(any());
    }

    @Test
    void 같은_요청에_같은_제품이_두_번_와도_한_번만_처리한다() {
        given(frequentlyUsedProductRepository.existsByUserIdAndProductId(userId, productId)).willReturn(false);

        int saved = service.saveBatch(userId, batch(productId, productId));

        assertThat(saved).isEqualTo(1);
        verify(frequentlyUsedProductRepository).save(any(FrequentlyUsedProduct.class));
    }

    @Test
    void 빈_값은_건너뛰고_나머지는_저장한다() {
        given(frequentlyUsedProductRepository.existsByUserIdAndProductId(userId, productId)).willReturn(false);
        FrequentlyUsedProductBatchRequest request = new FrequentlyUsedProductBatchRequest();
        ReflectionTestUtils.setField(request, "productIds", Arrays.asList(null, productId, null));

        int saved = service.saveBatch(userId, request);

        assertThat(saved).isEqualTo(1);
        verify(productRepository, never()).findById(null);
        verify(frequentlyUsedProductRepository).save(any(FrequentlyUsedProduct.class));
    }

    @Test
    void 없는_제품은_건너뛴다() {
        UUID missing = UUID.randomUUID();
        given(productRepository.findById(missing)).willReturn(Optional.empty());

        int saved = service.saveBatch(userId, batch(missing));

        assertThat(saved).isZero();
        verify(frequentlyUsedProductRepository, never()).save(any());
    }
}
