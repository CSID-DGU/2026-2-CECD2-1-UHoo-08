package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.response.ClarifyFieldResponse;
import com.capstone.backend.domain.recommendation.enums.ClarifyField;
import lombok.extern.slf4j.Slf4j;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * 되묻기 화면에서 물어볼 항목을 정한다.
 *
 * AI 가 빠진 필드 이름을 알려 주면 그대로 항목으로 바꾼다. 아직 알려 주지 않으면 시나리오로 정한다:
 * 예산 세트(S6_BUNDLE)는 예산과 구성, 그 외에는 문장 하나(종류)를 묻는다.
 * 모르는 필드 이름은 건너뛰고, 아는 항목이 하나도 없으면 문장 하나로 묻는다.
 */
@Slf4j
public final class ClarifyFieldMapper {

    static final String BUNDLE_SCENARIO = "S6_BUNDLE";

    private ClarifyFieldMapper() {
    }

    /**
     * @param scenario      job 의 시나리오. 판정 전이면 null
     * @param missingFields AI 가 알려 준 빠진 필드 이름. 아직 알려 주지 않으면 null
     */
    public static List<ClarifyFieldResponse> map(String scenario, List<String> missingFields) {
        if (missingFields == null || missingFields.isEmpty()) {
            return byScenario(scenario);
        }

        Set<ClarifyField> fields = new LinkedHashSet<>();
        for (String name : missingFields) {
            Optional<ClarifyField> field = ClarifyField.fromAiField(name);
            if (field.isPresent()) {
                fields.add(field.get());
            } else {
                log.warn("[ClarifyFieldMapper] 모르는 빠진 필드라 건너뜀: {}", name);
            }
        }
        if (fields.isEmpty()) {
            return List.of(ClarifyFieldResponse.of(ClarifyField.CATEGORY));
        }
        return fields.stream().map(ClarifyFieldResponse::of).toList();
    }

    private static List<ClarifyFieldResponse> byScenario(String scenario) {
        if (BUNDLE_SCENARIO.equals(scenario)) {
            return List.of(ClarifyFieldResponse.of(ClarifyField.BUDGET), ClarifyFieldResponse.of(ClarifyField.BUNDLE_STEPS));
        }
        return List.of(ClarifyFieldResponse.of(ClarifyField.CATEGORY));
    }
}
