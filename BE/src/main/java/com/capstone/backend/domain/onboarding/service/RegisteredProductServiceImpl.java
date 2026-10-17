package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductAddRequest;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductAddResponse;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductBatchRequest;
import com.capstone.backend.domain.onboarding.entity.Registered;
import com.capstone.backend.domain.onboarding.repository.RegisteredRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 온보딩에서 고르는 "자주 사용하는 제품".
 *
 * 취향을 알려 주는 정보라 registered_products 에만 둔다. 지금 가지고 쓰는 중인지는 알 수 없으므로
 * 사용 기록(user_products)에는 쓰지 않는다. 거기에 USING 으로 넣으면 추천 후보에서 빠지고 보유 제품으로 잡힌다.
 */
@Service
@RequiredArgsConstructor
public class RegisteredProductServiceImpl implements RegisteredProductService {

    private final ProductRepository productRepository;
    private final RegisteredRepository registeredRepository;
    private final UserRepository userRepository;

    @Override
    @Transactional
    public RegisteredProductAddResponse addFavoriteItem(UUID userId, RegisteredProductAddRequest request) {
        // 1. 상품 조회 또는 신규 생성
        boolean isNewProduct = false;
        Product product = productRepository.findByNameAndBrand(request.getName(), request.getBrand())
                .orElse(null);

        if (product == null) {
            isNewProduct = true;
            LocalDateTime now = LocalDateTime.now();
            product = Product.builder()
                    .name(request.getName())
                    .brand(request.getBrand())
                    .category(request.getCategory())
                    .imageUrl(request.getImageUrl())
                    .originalPrice(request.getLowestPrice())
                    .lowestPrice(request.getLowestPrice())
                    .lastUpdatedAt(now)
                    .build();
            product = productRepository.save(product);
        }

        // 2. 중복 등록 확인
        if (registeredRepository.existsByUserIdAndProductId(userId, product.getId())) {
            throw new BusinessException(ErrorCode.ALREADY_REGISTERED);
        }

        // 3. registered_products 저장
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        Registered registered = Registered.builder()
                .user(user)
                .product(product)
                .createdAt(LocalDateTime.now())
                .build();
        registered = registeredRepository.save(registered);

        return new RegisteredProductAddResponse(
                registered.getId(),
                product.getId(),
                product.getName(),
                product.getBrand(),
                product.getImageUrl(),
                isNewProduct
        );
    }

    @Override
    @Transactional
    public int saveBatch(UUID userId, RegisteredProductBatchRequest request) {
        if (request.getProductIds() == null || request.getProductIds().isEmpty()) return 0;

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        int saved = 0;
        // 같은 요청에 같은 제품이 두 번 들어와도 한 번만 처리한다
        for (UUID productId : request.getProductIds().stream().distinct().toList()) {
            Product product = productRepository.findById(productId).orElse(null);
            if (product == null) continue;

            if (!registeredRepository.existsByUserIdAndProductId(userId, productId)) {
                registeredRepository.save(Registered.builder()
                        .user(user)
                        .product(product)
                        .createdAt(LocalDateTime.now())
                        .build());
                saved++;
            }
        }
        return saved;
    }

    @Override
    @Transactional
    public void removeFavoriteItem(UUID userId, UUID registeredId) {
        Registered registered = registeredRepository.findByIdAndUserId(registeredId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        registeredRepository.delete(registered);
    }
}
