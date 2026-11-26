package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;
import com.capstone.backend.domain.onboarding.repository.FrequentlyUsedProductRepository;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/**
 * 온보딩에서 고르는 "자주 사용하는 제품".
 *
 * 취향을 알려 주는 정보라 frequently_used_products 에만 둔다. 지금 가지고 쓰는 중인지는 알 수 없으므로
 * 사용 기록(user_products)에는 쓰지 않는다. 거기에 USING 으로 넣으면 추천 후보에서 빠지고 보유 제품으로 잡힌다.
 */
@Service
@RequiredArgsConstructor
public class FrequentlyUsedProductServiceImpl implements FrequentlyUsedProductService {

    private final FrequentlyUsedProductRepository frequentlyUsedProductRepository;
    private final UserRepository userRepository;

    /** 없는 제품과 이미 고른 제품은 DB 가 한 문장 안에서 건너뛴다. 같은 요청이 겹쳐도 실패하지 않는다 */
    @Override
    @Transactional
    public int saveBatch(UUID userId, FrequentlyUsedProductBatchRequest request) {
        if (request.getProductIds() == null) return 0;
        // 같은 요청에 같은 제품이 두 번 들어와도 한 번만 처리하고, 빈 값은 없는 제품처럼 건너뛴다
        List<UUID> productIds = request.getProductIds().stream().filter(Objects::nonNull).distinct().toList();
        if (productIds.isEmpty()) return 0;

        if (!userRepository.existsById(userId)) {
            throw new BusinessException(ErrorCode.NOT_FOUND);
        }
        return frequentlyUsedProductRepository.insertIfAbsent(userId, productIds, LocalDateTime.now());
    }
}
