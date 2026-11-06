package com.capstone.backend.domain.onboarding.repository;

import com.capstone.backend.domain.onboarding.entity.FrequentlyUsedProduct;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

public interface FrequentlyUsedProductRepository extends JpaRepository<FrequentlyUsedProduct, UUID> {
    List<FrequentlyUsedProduct> findByUserId(UUID userId);

    /** 주어진 제품 중 이 사용자가 이미 고른 제품의 id. 일괄 등록에서 한 번에 확인한다 */
    @Query("SELECT f.product.id FROM FrequentlyUsedProduct f WHERE f.user.id = :userId AND f.product.id IN :productIds")
    List<UUID> findProductIdsByUserIdAndProductIdIn(@Param("userId") UUID userId,
                                                    @Param("productIds") Collection<UUID> productIds);
}
