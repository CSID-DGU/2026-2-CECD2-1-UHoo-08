package com.capstone.backend.domain.product.enums;

/**
 * user_products.usage_type. 산 제품 한 통이 지금 어떤 상태인지. DB 에 같은 세 값만 허용하는 CHECK 가 있다.
 *
 * user_products 는 사용 기록만 담는다. 조회는 product_views, 좋아요는 wishlists,
 * 온보딩의 자주 사용하는 제품은 registered_products 에 있다.
 * 보유 제품 API 의 상태와의 대응은 {@link UserProductStatus} 에 있다.
 */
public enum UsageType {

    /** 쓰고 있다. 같은 제품의 쓰는 중인 행은 하나만 둘 수 있다 */
    USING,
    /** 다 썼다 */
    USED,
    /** 버렸다 */
    DISCARDED
}
