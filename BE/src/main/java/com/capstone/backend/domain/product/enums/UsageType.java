package com.capstone.backend.domain.product.enums;

/**
 * user_products.usage_type. 사용자와 제품의 관계가 지금 어떤 상태인지.
 *
 * 조회 이력, 위시리스트, 보유 제품이 모두 같은 테이블에 쌓이므로 이 값으로 가른다.
 * 보유 제품 API 의 상태와의 대응은 {@link UserProductStatus} 에 있다.
 */
public enum UsageType {

    /** 조회 이력. 보유가 아니다 */
    VIEWED,
    /** 위시리스트. 아직 가진 것이 아니다 */
    INTERESTED,
    /** 쓰고 있다 */
    USING,
    /**
     * 예전 온보딩 등록이 남긴 값. 온보딩의 "자주 사용하는 제품"은 지금 쓰는 중인지 알 수 없어 사용 기록이 아니다.
     * 이제는 registered_products 에만 두고, 남은 행은 정리 마이그레이션에서 지운다. 보유로 보지 않는다.
     */
    ONBOARDING,
    /** 다 썼다 */
    USED,
    /** 버렸다 */
    DISCARDED
}
