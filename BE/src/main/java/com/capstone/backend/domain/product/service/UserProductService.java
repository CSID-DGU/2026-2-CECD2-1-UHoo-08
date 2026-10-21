package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.RegistrationSource;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 보유 제품(user_products). 산 제품 한 통마다 한 줄이고, 다시 사면 새 줄을 넣는다.
 *
 * 좋아요(wishlists)와 온보딩의 자주 사용하는 제품(registered_products)은 여기서 건드리지 않는다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserProductService {

    /** 쓰는 중인 행을 제품당 하나로 묶는 유니크 인덱스 */
    private static final String ACTIVE_ONCE_INDEX = "user_products_active_once";

    private final UserProductRepository userProductRepository;
    private final ProductRepository productRepository;
    private final PhotoRecognitionService photoRecognitionService;

    /**
     * 쓰는 중인 보유 제품으로 등록한다. 예전에 다 썼거나 버린 행은 되살리지 않고 그대로 둔다.
     * 사진으로 등록하면 인식 원본을 옮겨, 사용자가 고친 최종값과 비교해 인식 정확도를 잴 수 있게 한다.
     */
    @Transactional
    public UserProductCreateResponse create(UUID userId, UserProductCreateRequest request) {
        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        if (userProductRepository.existsByUserIdAndProductIdAndUsageType(userId, product.getId(), UsageType.USING)) {
            throw new BusinessException(ErrorCode.ALREADY_REGISTERED);
        }

        PhotoRecognition recognition = request.getRecognitionId() == null
                ? null
                : photoRecognitionService.getUsable(userId, toRecognitionId(request.getRecognitionId()));

        UserProduct userProduct = UserProduct.builder()
                .userId(userId)
                .productId(product.getId())
                .usageType(UsageType.USING)
                .openedAt(request.getOpenedAt() != null ? request.getOpenedAt() : LocalDate.now())
                .expiryDate(request.getExpiryDate())
                .paoMonths(request.getPaoMonths())
                .manufacturedAt(request.getManufacturedAt())
                .remainingPct(request.getRemainingPct())
                // 인식 결과로 등록했으면 사진 경로다. 정확도를 잴 때 경로를 기준으로 나누므로 요청 값보다 우선한다
                .source(recognition != null ? RegistrationSource.PHOTO : request.getSource())
                .recognizedRaw(recognition != null ? recognition.getRaw() : null)
                .createdAt(LocalDateTime.now())
                .updatedAt(OffsetDateTime.now())
                .build();

        UserProduct saved;
        try {
            saved = userProductRepository.saveAndFlush(userProduct);
        } catch (DataIntegrityViolationException e) {
            // 위 확인과 저장 사이에 같은 제품이 먼저 등록된 경우. 쓰는 중인 행은 제품당 하나다
            if (!String.valueOf(e.getMostSpecificCause().getMessage()).contains(ACTIVE_ONCE_INDEX)) {
                throw e;
            }
            log.warn("[UserProduct] 쓰는 중인 같은 제품이 동시에 등록됨: productId={}", product.getId());
            throw new BusinessException(ErrorCode.ALREADY_REGISTERED);
        }

        return new UserProductCreateResponse(saved.getId(), product.getId(), product.getName(), List.of());
    }

    private static UUID toRecognitionId(String recognitionId) {
        try {
            return UUID.fromString(recognitionId);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.RECOGNITION_NOT_FOUND);
        }
    }
}
