package com.capstone.backend.domain.home.enums;

/**
 * home_recommendations.kind. 홈 맞춤 추천 카드의 종류.
 */
public enum HomeRecommendationKind {

    /** 보유 제품끼리 성분이 충돌하는지 점검하고 대체 제품을 권한다 */
    ROUTINE,
    /** 4주 환경에 견줘 부족한 기능을 채울 제품을 권한다 */
    ENV
}
