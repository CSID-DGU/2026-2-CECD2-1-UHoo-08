package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.request.ClarificationRequest.Answers;

import java.util.ArrayList;
import java.util.List;

/**
 * 추가 질문의 답을 AI 에 보낼 문장 하나로 합친다. AI 계약(agent/clarify)이 답을 문자열 하나로 받기 때문이다.
 *
 * 예: {"budget":50000,"bundleSteps":["스킨","로션"]} → "예산 50000원, 구성: 스킨, 로션"
 * 비어 있는 답은 건너뛴다.
 */
public final class ClarifyAnswerFormatter {

    private ClarifyAnswerFormatter() {
    }

    /**
     * @param baseProductName 기준 제품 답을 화면에 보일 이름으로 바꾼 값. 기준 제품 답이 없으면 null
     */
    public static String format(Answers answers, String baseProductName) {
        List<String> parts = new ArrayList<>();
        if (answers.getBudget() != null) {
            parts.add("예산 " + answers.getBudget() + "원");
        }
        if (answers.getBundleSteps() != null) {
            List<String> steps = answers.getBundleSteps().stream()
                    .filter(step -> step != null && !step.isBlank())
                    .map(String::strip)
                    .toList();
            if (!steps.isEmpty()) {
                parts.add("구성: " + String.join(", ", steps));
            }
        }
        addIfPresent(parts, "종류: ", answers.getCategory());
        addIfPresent(parts, "기준 제품: ", baseProductName);
        addIfPresent(parts, "", answers.getText());
        return String.join(", ", parts);
    }

    private static void addIfPresent(List<String> parts, String prefix, String value) {
        if (value != null && !value.isBlank()) {
            parts.add(prefix + value.strip());
        }
    }
}
