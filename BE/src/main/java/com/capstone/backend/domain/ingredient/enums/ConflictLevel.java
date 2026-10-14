package com.capstone.backend.domain.ingredient.enums;

/**
 * ingredient_conflict_rules.level. 두 성분을 함께 쓸 때의 판정.
 */
public enum ConflictLevel {

    /** 함께 쓰지 않는다. 추천 후보에서 뺀다 */
    AVOID,
    /** 시간대를 나눠 쓴다. 후보에는 남기고 배지를 단다 */
    SEPARATE
}
