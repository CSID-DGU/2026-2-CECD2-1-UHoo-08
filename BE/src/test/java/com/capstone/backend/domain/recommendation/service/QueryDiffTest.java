package com.capstone.backend.domain.recommendation.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class QueryDiffTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode json(String value) throws Exception {
        return MAPPER.readTree(value);
    }

    @Test
    void 예산이_바뀌면_바뀐_값을_화살표로_잇는다() throws Exception {
        assertThat(QueryDiff.describe(
                json("{\"conditions\":[\"매트\"],\"budgetMax\":30000}"),
                json("{\"conditions\":[\"매트\"],\"budgetMax\":20000}")))
                .isEqualTo("3만원 이하 → 2만원 이하");
    }

    @Test
    void 더해진_조건은_조건_추가로_적는다() throws Exception {
        assertThat(QueryDiff.describe(
                json("{\"conditions\":[\"매트\"]}"),
                json("{\"conditions\":[\"매트\",\"무향\",\"민감성\"]}")))
                .isEqualTo("무향, 민감성 조건 추가");
    }

    @Test
    void 예산과_조건이_함께_바뀌면_예산부터_적는다() throws Exception {
        assertThat(QueryDiff.describe(
                json("{\"conditions\":[\"매트\",\"여름\"],\"budgetTotal\":100000}"),
                json("{\"conditions\":[\"매트\",\"무향\"],\"budgetMax\":20000,\"budgetTotal\":80000}")))
                .isEqualTo("2만원 이하 조건 추가, 총 10만원 → 총 8만원, 무향 조건 추가, 여름 조건 제외");
    }

    @Test
    void 빠진_예산은_조건_제외로_적는다() throws Exception {
        assertThat(QueryDiff.describe(json("{\"budgetMax\":30000}"), json("{}")))
                .isEqualTo("3만원 이하 조건 제외");
    }

    @Test
    void 달라진_것이_없으면_null() throws Exception {
        assertThat(QueryDiff.describe(
                json("{\"conditions\":[\"매트\"],\"budgetMax\":30000}"),
                json("{\"conditions\":[\"매트\"],\"budgetMax\":30000}")))
                .isNull();
    }

    @Test
    void 한쪽_요약이_없으면_null() throws Exception {
        assertThat(QueryDiff.describe(MissingNode.getInstance(), json("{\"conditions\":[\"무향\"]}"))).isNull();
        assertThat(QueryDiff.describe(json("{\"conditions\":[\"무향\"]}"), MissingNode.getInstance())).isNull();
    }
}
