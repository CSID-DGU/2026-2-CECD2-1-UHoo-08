package com.capstone.backend.domain.product.enums;

/** 보유 제품을 바꿀 때가 됐는지 */
public enum ReplaceStatus {

    /** 아직 괜찮다 */
    OK,
    /** 기한이 45일 이내로 남았다 */
    SOON,
    /** 기한이 지났다 */
    EXPIRED
}
