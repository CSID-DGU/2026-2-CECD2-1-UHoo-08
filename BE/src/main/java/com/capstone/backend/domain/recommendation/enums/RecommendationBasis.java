package com.capstone.backend.domain.recommendation.enums;

/**
 * recommendation_jobs.basis. 누구를 기준으로 추천하는지. AI 계약의 Target 과 같은 값이다.
 */
public enum RecommendationBasis {

    /** 내 피부 정보 기준 */
    SELF,
    /** 전체 인기 기준 */
    POPULAR,
    /** 다른 사람(선물 등). targetProfile 에 그 사람의 정보가 함께 온다 */
    OTHER
}
