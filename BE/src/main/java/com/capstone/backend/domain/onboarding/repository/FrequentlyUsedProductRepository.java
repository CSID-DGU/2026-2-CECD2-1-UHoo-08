package com.capstone.backend.domain.onboarding.repository;

import com.capstone.backend.domain.onboarding.entity.FrequentlyUsedProduct;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface FrequentlyUsedProductRepository extends JpaRepository<FrequentlyUsedProduct, UUID> {
    List<FrequentlyUsedProduct> findByUserId(UUID userId);
    boolean existsByUserIdAndProductId(UUID userId, UUID productId);
    long countByUserId(UUID userId);
}
