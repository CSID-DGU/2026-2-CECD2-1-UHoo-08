package com.capstone.backend.domain.recommendation.service;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;

/**
 * 조건 수정 이력에서 직전 단계와 이번 단계의 조건이 어떻게 달라졌는지 문구로 만든다.
 *
 * AI 결과의 query 요약끼리 비교한다. job 의 query_spec 은 AI 가 채우지 않아 쓸 수 없다.
 * 예산은 바뀐 값을 화살표로 잇고, 조건은 더해진 것과 빠진 것을 따로 적는다.
 * 예: "3만원 이하 → 2만원 이하, 무향 조건 추가"
 */
public final class QueryDiff {

    static final String SEPARATOR = ", ";

    private QueryDiff() {
    }

    /**
     * @param before 직전 단계의 query 요약. 없으면 MissingNode
     * @param after  이번 단계의 query 요약. 없으면 MissingNode
     * @return 달라진 내용. 둘 중 하나라도 없거나 달라진 것이 없으면 null
     */
    public static String describe(JsonNode before, JsonNode after) {
        if (!before.isObject() || !after.isObject()) {
            return null;
        }
        List<String> parts = new ArrayList<>();
        addBudget(parts, before.path("budgetMax"), after.path("budgetMax"), "", " 이하");
        addBudget(parts, before.path("budgetTotal"), after.path("budgetTotal"), "총 ", "");

        List<String> beforeConditions = SummaryBuilder.texts(before.path("conditions"));
        List<String> afterConditions = SummaryBuilder.texts(after.path("conditions"));
        List<String> added = afterConditions.stream().filter(c -> !beforeConditions.contains(c)).toList();
        List<String> removed = beforeConditions.stream().filter(c -> !afterConditions.contains(c)).toList();
        if (!added.isEmpty()) {
            parts.add(String.join(SEPARATOR, added) + " 조건 추가");
        }
        if (!removed.isEmpty()) {
            parts.add(String.join(SEPARATOR, removed) + " 조건 제외");
        }
        return parts.isEmpty() ? null : String.join(SEPARATOR, parts);
    }

    private static void addBudget(List<String> parts, JsonNode before, JsonNode after, String prefix, String suffix) {
        String beforeText = before.isIntegralNumber() ? prefix + SummaryBuilder.won(before.asLong()) + suffix : null;
        String afterText = after.isIntegralNumber() ? prefix + SummaryBuilder.won(after.asLong()) + suffix : null;
        if (beforeText == null && afterText == null || beforeText != null && beforeText.equals(afterText)) {
            return;
        }
        if (beforeText == null) {
            parts.add(afterText + " 조건 추가");
        } else if (afterText == null) {
            parts.add(beforeText + " 조건 제외");
        } else {
            parts.add(beforeText + " → " + afterText);
        }
    }
}
