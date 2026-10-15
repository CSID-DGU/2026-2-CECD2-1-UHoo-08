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
    /** 온보딩에서 등록했다. 쓰고 있는 것으로 본다 */
    ONBOARDING,
    /** 다 썼다 */
    USED,
    /** 버렸다 */
    DISCARDED
}
