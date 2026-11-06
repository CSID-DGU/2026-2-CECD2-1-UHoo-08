package com.capstone.backend.domain.product.enums;

/** 보유 제품 목록 정렬 */
public enum UserProductSort {

    /** 교체가 급한 순. 기한 지남 → 곧 교체 → 괜찮음, 같은 상태는 경과 비율이 큰 순 */
    REPLACE_NEED,
    /** 최근에 등록한 순 */
    RECENT
}
