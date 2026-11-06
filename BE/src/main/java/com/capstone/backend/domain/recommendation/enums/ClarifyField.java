package com.capstone.backend.domain.recommendation.enums;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

/**
 * 되물을 수 있는 항목. AI 가 빠졌다고 알려 주는 필드 이름(QuerySpec 기준)과 화면에 보여 줄 질문을 잇는다.
 */
public enum ClarifyField {

    BUDGET("budget.total", "budget", "예산은 얼마로 볼까요?", ClarifyInputType.AMOUNT, List.of(30000, 50000, 100000)),
    BUNDLE_STEPS("bundle_steps", "bundleSteps", "어떤 화장품으로 구성할까요?", ClarifyInputType.TEXT_LIST, null),
    CATEGORY("category", "category", "어떤 종류를 찾으세요?", ClarifyInputType.TEXT, null),
    BASE_PRODUCT("base_product_ref", "baseProduct", "어떤 제품을 기준으로 볼까요?", ClarifyInputType.PRODUCT, null);

    private final String aiField;
    private final String key;
    private final String label;
    private final ClarifyInputType inputType;
    private final List<Integer> presets;

    ClarifyField(String aiField, String key, String label, ClarifyInputType inputType, List<Integer> presets) {
        this.aiField = aiField;
        this.key = key;
        this.label = label;
        this.inputType = inputType;
        this.presets = presets;
    }

    public String key() {
        return key;
    }

    public String label() {
        return label;
    }

    public ClarifyInputType inputType() {
        return inputType;
    }

    /** 빠른 선택값. 없으면 null */
    public List<Integer> presets() {
        return presets;
    }

    /** AI 가 알려 준 빠진 필드 이름으로 찾는다 */
    public static Optional<ClarifyField> fromAiField(String aiField) {
        return Arrays.stream(values()).filter(field -> field.aiField.equals(aiField)).findFirst();
    }
}
