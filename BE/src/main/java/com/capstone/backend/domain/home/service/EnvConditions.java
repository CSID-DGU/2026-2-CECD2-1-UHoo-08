package com.capstone.backend.domain.home.service;

import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * AI 홈 환경 추천 결과의 조건 블록(conditions[{key,label,basis,covered,coveredBy}])을 읽는다. 환경 요약과 환경 기반 추천이 함께 쓴다.
 *
 * 조건 블록을 싣기 전의 결과는 행이 있어도 분석 전으로 본다. 빈 목록으로 내리면 채울 조건이 없는 것처럼 보인다.
 */
public final class EnvConditions {

    private EnvConditions() {
    }

    /** 결과에 조건 블록이 없으면 비어 있다. key 가 없는 항목은 건너뛴다 */
    public static Optional<List<Condition>> parse(JsonNode result) {
        JsonNode items = result.path("conditions");
        if (!items.isArray()) {
            return Optional.empty();
        }
        List<Condition> conditions = new ArrayList<>();
        items.forEach(item -> {
            String key = item.path("key").asText(null);
            if (key == null || key.isBlank()) {
                return;
            }
            conditions.add(new Condition(key, item.path("label").asText(key), item.path("basis").asText(null),
                    item.path("covered").asBoolean(false), item.path("coveredBy").asText(null)));
        });
        return Optional.of(conditions);
    }
}
