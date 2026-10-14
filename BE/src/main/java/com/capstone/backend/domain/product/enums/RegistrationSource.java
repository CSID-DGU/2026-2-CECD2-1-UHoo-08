package com.capstone.backend.domain.product.enums;

/**
 * user_products.source. 보유 제품을 어떤 경로로 등록했는지. 사진 인식 정확도를 재려면 구분이 필요하다.
 */
public enum RegistrationSource {

    /** 사진으로 인식해 등록 */
    PHOTO,
    /** 직접 골라 등록 */
    MANUAL
}
