package com.capstone.backend.domain.home.enums;

/**
 * 홈 맞춤 추천 카드의 상태. 화면이 카드 문구를 고르는 데 쓴다.
 */
public enum HomeRecommendationState {

    /** 권할 제품이 있다 */
    READY,
    /** 계산했지만 권할 제품이 없다. 지금 루틴으로 충분하다 */
    FULLY_COVERED,
    /** 아직 계산 전이다 */
    NOT_READY
}
