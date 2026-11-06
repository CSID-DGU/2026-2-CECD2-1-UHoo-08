package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;
import com.capstone.backend.domain.onboarding.entity.FrequentlyUsedProduct;
import com.capstone.backend.domain.onboarding.repository.FrequentlyUsedProductRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 온보딩에서 고르는 "자주 사용하는 제품".
 *
 * 취향을 알려 주는 정보라 frequently_used_products 에만 둔다. 지금 가지고 쓰는 중인지는 알 수 없으므로
 * 사용 기록(user_products)에는 쓰지 않는다. 거기에 USING 으로 넣으면 추천 후보에서 빠지고 보유 제품으로 잡힌다.
 */
@Service
@RequiredArgsConstructor
public class FrequentlyUsedProductServiceImpl implements FrequentlyUsedProductService {

    private final ProductRepository productRepository;
    private final FrequentlyUsedProductRepository frequentlyUsedProductRepository;
    private final UserRepository userRepository;

    /** 제품과 이미 고른 제품을 한 번에 읽어, 요청한 제품 수와 상관없이 조회 수가 같다 */
    @Override
    @Transactional
    public int saveBatch(UUID userId, FrequentlyUsedProductBatchRequest request) {
        if (request.getProductIds() == null) return 0;
        // 같은 요청에 같은 제품이 두 번 들어와도 한 번만 처리하고, 빈 값은 없는 제품처럼 건너뛴다
        List<UUID> productIds = request.getProductIds().stream().filter(Objects::nonNull).distinct().toList();
        if (productIds.isEmpty()) return 0;

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        Map<UUID, Product> products = productRepository.findAllById(productIds).stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));
        Set<UUID> alreadyChosen = new HashSet<>(
                frequentlyUsedProductRepository.findProductIdsByUserIdAndProductIdIn(userId, productIds));

        LocalDateTime now = LocalDateTime.now();
        List<FrequentlyUsedProduct> rows = productIds.stream()
                .filter(products::containsKey)
                .filter(productId -> !alreadyChosen.contains(productId))
                .map(productId -> FrequentlyUsedProduct.builder()
                        .user(user)
                        .product(products.get(productId))
                        .createdAt(now)
                        .build())
                .toList();
        frequentlyUsedProductRepository.saveAll(rows);
        return rows.size();
    }
}
