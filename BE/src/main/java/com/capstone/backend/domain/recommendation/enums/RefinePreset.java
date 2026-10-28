package com.capstone.backend.domain.recommendation.enums;

import java.util.Arrays;
import java.util.Optional;

/**
 * 조건 수정에서 고를 수 있는 조건. 화면에 보일 이름과 AI 에 보낼 문장을 가진다.
 * recommendation_jobs.refine_presets 에 이름 그대로 저장된다.
 */
public enum RefinePreset {

    CHEAPER("더 저렴하게", "더 저렴한 제품으로"),
    UNSCENTED("향 없는 걸로", "무향 제품으로"),
    HIGH_COVERAGE("커버력 높게", "커버력이 높은 제품으로"),
    LONG_LASTING("지속력 좋은", "지속력이 좋은 제품으로"),
    UV_PROTECT("자외선 차단", "자외선 차단이 되는 제품으로"),
    SENSITIVE_OK("민감성도 괜찮은", "민감한 피부에도 괜찮은 제품으로");

    private final String label;
    private final String sentence;

    RefinePreset(String label, String sentence) {
        this.label = label;
        this.sentence = sentence;
    }

    public String label() {
        return label;
    }

    /** AI 에 보낼 문장 */
    public String sentence() {
        return sentence;
    }

    /** 저장된 키로 찾는다. 모르는 키면 비어 있다 */
    public static Optional<RefinePreset> fromKey(String key) {
        return Arrays.stream(values()).filter(preset -> preset.name().equals(key)).findFirst();
    }
}
