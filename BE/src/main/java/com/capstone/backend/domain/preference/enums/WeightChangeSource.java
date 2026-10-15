package com.capstone.backend.domain.preference.enums;

/**
 * preference_weight_changes.source. 무엇 때문에 가중치가 움직였는지.
 */
public enum WeightChangeSource {

    /** 추천 피드백. source_ref 는 recommendation_feedback.id */
    FEEDBACK,
    /** 조건 수정에서 반복되는 패턴. source_ref 는 패턴 키(CHEAPER 등) */
    REFINE_PATTERN
}
