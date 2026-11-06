package com.capstone.backend.domain.recommendation.enums;

import java.util.Arrays;

/**
 * 추천 결과의 카테고리. AI 계약의 Category 와 같은 네 값이고, 화면에 보일 한글 이름을 가진다.
 */
public enum RecommendationCategory {

    BASE("base", "베이스 메이크업"),
    SUN("sun", "선케어"),
    LIP("lip", "립 메이크업"),
    SKINCARE("skincare", "스킨케어");

    private final String value;
    private final String label;

    RecommendationCategory(String value, String label) {
        this.value = value;
        this.label = label;
    }

    public String label() {
        return label;
    }

    /** AI 결과에 담긴 값으로 찾는다. 비어 있거나 모르는 값이면 null */
    public static RecommendationCategory from(String value) {
        return Arrays.stream(values()).filter(category -> category.value.equals(value)).findFirst().orElse(null);
    }

    /** AI 결과에 담긴 값의 한글 이름. 비어 있거나 모르는 값이면 null */
    public static String labelOf(String value) {
        RecommendationCategory category = from(value);
        return category == null ? null : category.label;
    }
}
