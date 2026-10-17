package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.ProductView;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface ProductViewRepository extends JpaRepository<ProductView, ProductView.Key> {

    /**
     * 조회를 남긴다. 처음 보면 한 줄을 넣고, 이미 있으면 마지막 조회 시각과 횟수만 바꾼다.
     *
     * 읽고 나서 쓰면 같은 제품을 동시에 두 번 볼 때 둘 다 "없음"으로 읽고 넣다가 키가 겹쳐 실패한다.
     * 한 문장으로 처리해 DB 가 합치게 한다.
     */
    @Modifying
    @Query(value = """
            INSERT INTO product_views (user_id, product_id, first_viewed_at, last_viewed_at, view_count)
            VALUES (:userId, :productId, now(), now(), 1)
            ON CONFLICT (user_id, product_id) DO UPDATE
            SET last_viewed_at = now(),
                view_count = product_views.view_count + 1
            """, nativeQuery = true)
    void upsertView(@Param("userId") UUID userId, @Param("productId") UUID productId);

    /** 마지막으로 본 순서대로 제품 id 를 읽는다 */
    @Query("SELECT v.productId FROM ProductView v WHERE v.userId = :userId ORDER BY v.lastViewedAt DESC")
    List<UUID> findRecentProductIds(@Param("userId") UUID userId, Pageable pageable);
}
