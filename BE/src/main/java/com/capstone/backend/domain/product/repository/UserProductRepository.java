package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.UsageType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

/**
 * user_products 는 사용 기록이다. 산 제품 한 통마다 한 줄이고, 다시 사면 새 줄을 넣는다.
 *
 * 상태를 바꾸거나 지울 때는 항상 행 하나(id)를 대상으로 한다. (user, product) 조건으로 한꺼번에 바꾸거나 지우면
 * 지난번에 다 쓴 기록까지 함께 덮이거나 사라진다. 조회는 product_views, 좋아요는 wishlists,
 * 온보딩의 자주 사용하는 제품은 registered_products 에 따로 있다.
 */
public interface UserProductRepository extends JpaRepository<UserProduct, UUID> {

    /** 이 제품을 이 상태로 가진 행이 있는지. 쓰는 중(USING) 행은 제품당 하나만 둘 수 있다 */
    boolean existsByUserIdAndProductIdAndUsageType(UUID userId, UUID productId, UsageType usageType);
}
