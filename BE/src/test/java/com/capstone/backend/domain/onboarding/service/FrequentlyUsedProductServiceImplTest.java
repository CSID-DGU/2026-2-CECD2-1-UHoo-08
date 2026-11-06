package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;
import com.capstone.backend.domain.onboarding.repository.FrequentlyUsedProductRepository;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

/**
 * 온보딩의 "자주 사용하는 제품"은 frequently_used_products 에만 남는다.
 * 서비스가 사용 기록(UserProductRepository)을 아예 의존하지 않으므로, 사용 기록을 건드릴 길이 없다.
 * 없는 제품과 이미 고른 제품을 건너뛰는 일은 DB 가 INSERT 한 문장 안에서 한다.
 */
@ExtendWith(MockitoExtension.class)
class FrequentlyUsedProductServiceImplTest {

    @Mock
    FrequentlyUsedProductRepository frequentlyUsedProductRepository;
    @Mock
    UserRepository userRepository;
    @InjectMocks
    FrequentlyUsedProductServiceImpl service;

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();
    private final UUID otherId = UUID.randomUUID();

    private FrequentlyUsedProductBatchRequest batch(UUID... ids) {
        FrequentlyUsedProductBatchRequest request = new FrequentlyUsedProductBatchRequest();
        ReflectionTestUtils.setField(request, "productIds", Arrays.asList(ids));
        return request;
    }

    @Test
    void 고른_제품을_한_문장으로_넣고_새로_넣은_개수를_돌려준다() {
        given(userRepository.existsById(userId)).willReturn(true);
        given(frequentlyUsedProductRepository.insertIfAbsent(eq(userId), eq(List.of(productId, otherId)), any()))
                .willReturn(1);

        assertThat(service.saveBatch(userId, batch(productId, otherId))).isEqualTo(1);
    }

    @Test
    void 같은_제품과_빈_값은_한_번만_넘긴다() {
        given(userRepository.existsById(userId)).willReturn(true);
        given(frequentlyUsedProductRepository.insertIfAbsent(eq(userId), any(), any())).willReturn(1);

        service.saveBatch(userId, batch(null, productId, productId, null));

        verify(frequentlyUsedProductRepository).insertIfAbsent(eq(userId), eq(List.of(productId)), any());
    }

    @Test
    void 빈_요청이면_아무것도_하지_않는다() {
        assertThat(service.saveBatch(userId, batch())).isZero();
        assertThat(service.saveBatch(userId, batch((UUID) null))).isZero();
        FrequentlyUsedProductBatchRequest noList = new FrequentlyUsedProductBatchRequest();
        assertThat(service.saveBatch(userId, noList)).isZero();

        verifyNoInteractions(userRepository, frequentlyUsedProductRepository);
    }

    @Test
    void 없는_사용자면_NOT_FOUND다() {
        given(userRepository.existsById(userId)).willReturn(false);

        assertThatThrownBy(() -> service.saveBatch(userId, batch(productId)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
        verifyNoInteractions(frequentlyUsedProductRepository);
    }
}
