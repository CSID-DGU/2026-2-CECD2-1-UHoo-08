package com.capstone.backend.domain.onboarding.repository;

import com.capstone.backend.domain.onboarding.entity.FrequentlyUsedProduct;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.UUID;

public interface FrequentlyUsedProductRepository extends JpaRepository<FrequentlyUsedProduct, UUID> {
    List<FrequentlyUsedProduct> findByUserId(UUID userId);

    /**
     * 주어진 제품 중 있는 제품을 자주 사용하는 제품으로 넣고, 새로 넣은 개수를 돌려준다. 이미 고른 제품은 건너뛴다.
     *
     * 읽고 나서 쓰면 같은 사용자의 요청 두 개가 겹칠 때 둘 다 "없음"으로 읽고 넣다가 유니크 제약에 걸려 요청 전체가 실패한다.
     * 한 문장으로 처리해 DB 가 겹친 행을 건너뛰게 한다.
     */
    @Modifying
    @Query(value = """
            INSERT INTO frequently_used_products (id, user_id, product_id, created_at)
            SELECT gen_random_uuid(), :userId, p.product_id, :now
            FROM products p
            WHERE p.product_id IN (:productIds)
            ON CONFLICT (user_id, product_id) DO NOTHING
            """, nativeQuery = true)
    int insertIfAbsent(@Param("userId") UUID userId, @Param("productIds") Collection<UUID> productIds,
                       @Param("now") LocalDateTime now);
}
