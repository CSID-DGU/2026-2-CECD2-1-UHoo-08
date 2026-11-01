package com.capstone.backend.domain.home.service;

import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Pair;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class RoutineCheckBuilderTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode sample() throws Exception {
        try (InputStream in = RoutineCheckBuilderTest.class.getResourceAsStream("/ai-results/HOME_ROUTINE.json")) {
            return MAPPER.readTree(in);
        }
    }

    @Test
    void 점검_블록을_꺼내고_쌍은_같이_쓰지_말_것부터_정렬한다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(sample(), 5);

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getProductCount()).isEqualTo(5);
        assertThat(response.getCounts().getOk()).isEqualTo(7);
        assertThat(response.getCounts().getSeparate()).isEqualTo(2);
        assertThat(response.getCounts().getAvoid()).isEqualTo(1);
        assertThat(response.getPairs())
                .extracting(Pair::getLevel, pair -> pair.getA().getName(), pair -> pair.getB().getName())
                .containsExactly(
                        tuple(CompatibilityLevel.AVOID, "레티놀 앰플", "비타민C 세럼"),
                        tuple(CompatibilityLevel.SEPARATE, "AHA 토너", "레티놀 앰플"),
                        tuple(CompatibilityLevel.OK, "수분 토너", "수분 크림"));
        assertThat(response.getPairs().get(0).getTitle()).isEqualTo("같이 쓰지 마세요");
        assertThat(response.getReplacement().getReplaceTarget().getName()).isEqualTo("비타민C 세럼");
        assertThat(response.getReplacement().getItems().get(0).getPrice()).isEqualTo(19800);
        assertThat(response.getReplacement().getItems().get(0).getBadge()).isEqualTo("쓰시는 제품 5개와 모두 괜찮아요");
        assertThat(response.getSchedule().getMorning()).containsExactly("수분 토너", "톤업 세럼", "선크림");
        assertThat(response.getSchedule().getTip()).isEqualTo("AHA 먼저, 레티놀은 하루 걸러 쓰세요");
        assertThat(response.getUncomparedCount()).isEqualTo(1);
    }

    @Test
    void 보유_제품이_2개_미만이면_쌍과_개수와_대체_제안을_비우고_사용_순서는_남긴다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(sample(), 1);

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getCounts().getAvoid()).isZero();
        assertThat(response.getCounts().getOk()).isZero();
        assertThat(response.getReplacement()).isNull();
        assertThat(response.getSchedule().getEvening()).hasSize(3);
    }

    @Test
    void 결과가_없거나_쌍_목록이_없으면_점검_전이고_모두_비운다() throws Exception {
        for (JsonNode result : new JsonNode[]{MissingNode.getInstance(),
                MAPPER.readTree("{\"scenario\":\"HOME_ROUTINE\",\"items\":[]}")}) {
            RoutineCheckResponse response = RoutineCheckBuilder.build(result, 3);

            assertThat(response.isChecked()).isFalse();
            assertThat(response.getProductCount()).isEqualTo(3);
            assertThat(response.getPairs()).isEmpty();
            assertThat(response.getReplacement()).isNull();
            assertThat(response.getSchedule().getMorning()).isEmpty();
            assertThat(response.getUncomparedCount()).isZero();
        }
    }

    @Test
    void 점검했지만_충돌이_없으면_점검은_했고_쌍은_비어_있다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(MAPPER.readTree("{\"pairs\":[]}"), 3);

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getCounts().getAvoid()).isZero();
        assertThat(response.getReplacement()).isNull();
    }

    @Test
    void 개수가_없으면_쌍에서_세고_궁합을_모르는_쌍은_뺀다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(MAPPER.readTree("""
                {"pairs":[{"level":"OK"},{"level":"AVOID"},{"level":"MAYBE"},{"level":"OK"}]}"""), 3);

        assertThat(response.getPairs()).extracting(Pair::getLevel)
                .containsExactly(CompatibilityLevel.AVOID, CompatibilityLevel.OK, CompatibilityLevel.OK);
        assertThat(response.getCounts().getOk()).isEqualTo(2);
        assertThat(response.getCounts().getSeparate()).isZero();
        assertThat(response.getCounts().getAvoid()).isEqualTo(1);
    }
}
