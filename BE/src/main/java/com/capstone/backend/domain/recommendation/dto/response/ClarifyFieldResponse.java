package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.enums.ClarifyField;
import com.capstone.backend.domain.recommendation.enums.ClarifyInputType;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** 되묻기에서 물어볼 항목 하나 */
@Getter
@AllArgsConstructor
public class ClarifyFieldResponse {
    /** budget, bundleSteps, category, baseProduct */
    private String key;
    private String label;
    private ClarifyInputType inputType;
    /** 빠른 선택값. 없으면 null */
    private List<Integer> presets;

    public static ClarifyFieldResponse of(ClarifyField field) {
        return new ClarifyFieldResponse(field.key(), field.label(), field.inputType(), field.presets());
    }
}
