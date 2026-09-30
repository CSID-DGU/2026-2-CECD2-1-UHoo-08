package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.UserProduct;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

public interface UserProductRepository extends JpaRepository<UserProduct, UUID> {
    boolean existsByUserIdAndProductId(UUID userId, UUID productId);

    /**
     * 보유 행이 이미 있는지 본다.
     *
     * user_products에는 조회 이력(VIEWED)과 위시리스트(INTERESTED)도 함께 쌓인다.
     * 그것까지 세면 전에 본 적 있거나 담아 둔 제품을 등록할 때 "이미 있다"로
     * 판단해 보유 행이 만들어지지 않는다.
     *
     * 다 썼거나(USED) 버린(DISCARDED) 행은 보유 행으로 센다. 같은 제품의 기록은
     * 한 줄로 둔다는 뜻이고, 다시 등록하는 경우는 {@link #reactivateOwnedProduct}
     * 가 그 행을 USING으로 되돌린다.
     */
    @Query("SELECT COUNT(up) > 0 FROM UserProduct up " +
           "WHERE up.userId = :userId AND up.productId = :productId " +
           "AND up.usageType IN ('USING', 'ONBOARDING', 'USED', 'DISCARDED')")
    boolean existsOwnedByUserIdAndProductId(@Param("userId") UUID userId,
                                            @Param("productId") UUID productId);

    /**
     * 다 썼거나 버렸거나 위시리스트에 담아 둔 제품을 등록할 때 원래 행을 올린다.
     *
     * 새 행을 넣지 않는 이유는 두 가지다. optical_measurements와 risk_events가
     * 이 행의 id를 참조하고 있어 새로 만들면 측정 이력이 끊기고, 위시리스트 행을
     * 그대로 두면 이미 산 제품이 위시리스트에 계속 남는다.
     */
    @Modifying
    @Transactional
    @Query("UPDATE UserProduct up SET up.usageType = 'USING' " +
           "WHERE up.userId = :userId AND up.productId = :productId " +
           "AND up.usageType IN ('USED', 'DISCARDED', 'INTERESTED')")
    int reactivateOwnedProduct(@Param("userId") UUID userId,
                               @Param("productId") UUID productId);

    /**
     * 보유 행만 지운다.
     *
     * 조회 이력과 위시리스트까지 지우면 최근 본 상품과 찜 목록에서 사라진다.
     * 등록을 취소한 것과 본 적 없다는 것은 다른 이야기다.
     */
    @Modifying
    @Transactional
    @Query("DELETE FROM UserProduct up " +
           "WHERE up.userId = :userId AND up.productId = :productId " +
           "AND up.usageType IN ('USING', 'ONBOARDING', 'USED', 'DISCARDED')")
    void deleteOwnedByUserIdAndProductId(@Param("userId") UUID userId,
                                         @Param("productId") UUID productId);

    @Modifying
    @Transactional
    @Query("DELETE FROM UserProduct up WHERE up.userId = :userId AND up.productId = :productId")
    void deleteByUserIdAndProductId(@Param("userId") UUID userId, @Param("productId") UUID productId);

    @Modifying
    @Transactional
    @Query("DELETE FROM UserProduct up WHERE up.userId = :userId AND up.productId = :productId AND up.usageType = :usageType")
    void deleteByUserIdAndProductIdAndUsageType(@Param("userId") UUID userId,
                                                @Param("productId") UUID productId,
                                                @Param("usageType") String usageType);

    @Query("SELECT up.productId FROM UserProduct up WHERE up.userId = :userId AND up.usageType = 'VIEWED' ORDER BY up.createdAt DESC")
    List<UUID> findRecentViewedProductIds(@Param("userId") UUID userId, Pageable pageable);
}
