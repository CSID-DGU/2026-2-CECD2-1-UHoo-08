package com.capstone.backend.common.util;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;
import org.springframework.context.annotation.Import;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

// 앱과 같은 ObjectMapper(application.yml 의 spring.jackson 설정 포함)로 확인한다
@JsonTest
@Import(JsonUtil.class)
class JsonUtilTest {

    @Autowired
    ObjectMapper objectMapper;
    @Autowired
    JsonUtil jsonUtil;

    record Step(String key, String label, String state) {
    }

    record Snapshot(String query, LocalDate date) {
    }

    @Test
    void jsonb_문자열을_트리로_읽는다() {
        JsonNode node = jsonUtil.readTree("{\"mainRecommendations\":[{\"productId\":\"p1\",\"score\":0.9}]}");

        assertThat(node.path("mainRecommendations").get(0).path("productId").asText()).isEqualTo("p1");
        assertThat(node.path("mainRecommendations").get(0).path("score").asDouble()).isEqualTo(0.9);
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"  "})
    void 비어_있으면_MissingNode라_path를_이어_써도_안전하다(String json) {
        JsonNode node = jsonUtil.readTree(json);

        assertThat(node.isMissingNode()).isTrue();
        assertThat(node.path("a").path("b").asText("기본값")).isEqualTo("기본값");
    }

    @Test
    void 타입으로_읽는다() {
        List<Step> steps = jsonUtil.read(
                "[{\"key\":\"parse\",\"label\":\"조건 이해\",\"state\":\"DONE\"}]",
                new TypeReference<List<Step>>() {});
        Snapshot snapshot = jsonUtil.read("{\"query\":\"수분크림\",\"date\":\"2026-10-14\"}", Snapshot.class);

        assertThat(steps).containsExactly(new Step("parse", "조건 이해", "DONE"));
        assertThat(snapshot).isEqualTo(new Snapshot("수분크림", LocalDate.of(2026, 10, 14)));
    }

    @Test
    void 비어_있으면_타입_읽기는_null이다() {
        assertThat(jsonUtil.read(null, Snapshot.class)).isNull();
        assertThat(jsonUtil.read("", new TypeReference<Map<String, Object>>() {})).isNull();
    }

    @ParameterizedTest
    @ValueSource(strings = {"{\"a\":", "not json", "{'a':1}"})
    void 깨진_JSON은_INTERNAL_ERROR다(String json) {
        assertThatThrownBy(() -> jsonUtil.readTree(json))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.INTERNAL_ERROR);
        assertThatThrownBy(() -> jsonUtil.read(json, Snapshot.class))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.INTERNAL_ERROR);
    }

    @Test
    void 객체를_jsonb_문자열로_쓰고_다시_읽으면_같다() {
        Snapshot snapshot = new Snapshot("수분크림", LocalDate.of(2026, 10, 14));

        String json = jsonUtil.write(snapshot);

        assertThat(json).contains("\"date\":\"2026-10-14\"");   // 날짜는 배열이 아니라 문자열
        assertThat(jsonUtil.read(json, Snapshot.class)).isEqualTo(snapshot);
    }

    @Test
    void 트리도_쓸_수_있고_null은_null이다() {
        ObjectNode node = objectMapper.createObjectNode().put("budget_fit", 0.05);

        assertThat(jsonUtil.write(node)).isEqualTo("{\"budget_fit\":0.05}");
        assertThat(jsonUtil.write(null)).isNull();
    }

    @Test
    void 트리를_타입으로_바꾼다() {
        JsonNode node = jsonUtil.readTree("{\"key\":\"rank\",\"label\":\"순위 매기기\",\"state\":\"RUNNING\"}");

        assertThat(jsonUtil.convert(node, Step.class)).isEqualTo(new Step("rank", "순위 매기기", "RUNNING"));
        assertThat(jsonUtil.convert(jsonUtil.readTree(null), Step.class)).isNull();
    }
}
