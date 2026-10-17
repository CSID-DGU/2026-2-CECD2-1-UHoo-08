package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductBatchRequest;
import com.capstone.backend.domain.onboarding.entity.Registered;
import com.capstone.backend.domain.onboarding.repository.RegisteredRepository;
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

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 온보딩의 "자주 사용하는 제품"은 registered_products 에만 남는다.
 * 서비스가 사용 기록(UserProductRepository)을 아예 의존하지 않으므로, 사용 기록을 건드릴 길이 없다.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class RegisteredProductServiceImplTest {

    @Mock
    ProductRepository productRepository;
    @Mock
    RegisteredRepository registeredRepository;
    @Mock
    UserRepository userRepository;
    @InjectMocks
    RegisteredProductServiceImpl service;

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

    private RegisteredProductBatchRequest batch(UUID... ids) {
        RegisteredProductBatchRequest request = new RegisteredProductBatchRequest();
        ReflectionTestUtils.setField(request, "productIds", List.of(ids));
        return request;
    }

    @Test
    void 고른_제품을_registered_products에_남긴다() {
        given(registeredRepository.existsByUserIdAndProductId(userId, productId)).willReturn(false);

        int saved = service.saveBatch(userId, batch(productId));

        assertThat(saved).isEqualTo(1);
        ArgumentCaptor<Registered> captor = ArgumentCaptor.forClass(Registered.class);
        verify(registeredRepository).save(captor.capture());
        assertThat(captor.getValue().getUser()).isEqualTo(user);
        assertThat(captor.getValue().getProduct()).isEqualTo(product);
    }

    @Test
    void 이미_고른_제품은_다시_넣지_않는다() {
        // 온보딩 화면은 다시 들어와 완료할 수 있다
        given(registeredRepository.existsByUserIdAndProductId(userId, productId)).willReturn(true);

        int saved = service.saveBatch(userId, batch(productId));

        assertThat(saved).isZero();
        verify(registeredRepository, never()).save(any());
    }

    @Test
    void 같은_요청에_같은_제품이_두_번_와도_한_번만_처리한다() {
        given(registeredRepository.existsByUserIdAndProductId(userId, productId)).willReturn(false);

        int saved = service.saveBatch(userId, batch(productId, productId));

        assertThat(saved).isEqualTo(1);
        verify(registeredRepository).save(any(Registered.class));
    }

    @Test
    void 없는_제품은_건너뛴다() {
        UUID missing = UUID.randomUUID();
        given(productRepository.findById(missing)).willReturn(Optional.empty());

        int saved = service.saveBatch(userId, batch(missing));

        assertThat(saved).isZero();
        verify(registeredRepository, never()).save(any());
    }

    @Test
    void 등록을_취소하면_registered_products의_그_행만_지운다() {
        UUID registeredId = UUID.randomUUID();
        Registered registered = Registered.builder().id(registeredId).user(user).product(product)
                .createdAt(LocalDateTime.now()).build();
        given(registeredRepository.findByIdAndUserId(registeredId, userId)).willReturn(Optional.of(registered));

        service.removeFavoriteItem(userId, registeredId);

        verify(registeredRepository).delete(registered);
    }

    @Test
    void 남의_등록은_취소할_수_없다() {
        UUID registeredId = UUID.randomUUID();
        given(registeredRepository.findByIdAndUserId(registeredId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.removeFavoriteItem(userId, registeredId))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
        verify(registeredRepository, never()).delete(any());
    }
}
