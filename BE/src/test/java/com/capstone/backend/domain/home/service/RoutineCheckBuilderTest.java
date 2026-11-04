package com.capstone.backend.domain.home.service;

import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Pair;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class RoutineCheckBuilderTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 샘플 결과가 가리키는 보유 제품 5개 */
    static final Set<UUID> SAMPLE_USING_IDS = IntStream.rangeClosed(1, 5)
            .mapToObj(RoutineCheckBuilderTest::sampleId).collect(Collectors.toSet());

    static UUID sampleId(int n) {
        return UUID.fromString("aaaaaaaa-0000-0000-0000-00000000000" + n);
    }

    private static ObjectNode sample() throws Exception {
        try (InputStream in = RoutineCheckBuilderTest.class.getResourceAsStream("/ai-results/HOME_ROUTINE.json")) {
            return (ObjectNode) MAPPER.readTree(in);
        }
    }

    @Test
    void 점검_블록을_꺼내고_쌍은_같이_쓰지_말_것부터_정렬한다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(sample(), SAMPLE_USING_IDS);

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
    void 점검_뒤에_다_쓰거나_지운_제품이_쌍에_있으면_지난_결과로_보고_점검_전이다() throws Exception {
        Set<UUID> afterFinishing = SAMPLE_USING_IDS.stream()
                .filter(id -> !id.equals(sampleId(3))).collect(Collectors.toSet());

        RoutineCheckResponse response = RoutineCheckBuilder.build(sample(), afterFinishing);

        assertThat(response.isChecked()).isFalse();
        assertThat(response.getProductCount()).isEqualTo(4);
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getReplacement()).isNull();
        assertThat(response.getSchedule().getMorning()).isEmpty();
    }

    @Test
    void 대체_제안의_바꿀_제품이_지금_쓰는_중이_아니면_점검_전이다() throws Exception {
        ObjectNode result = sample();
        ((ObjectNode) result.path("replacement").path("replaceTarget"))
                .put("userProductId", UUID.randomUUID().toString());

        assertThat(RoutineCheckBuilder.build(result, SAMPLE_USING_IDS).isChecked()).isFalse();
    }

    @Test
    void 쌍의_보유_제품_ID가_없거나_형식이_틀리면_점검_전이다() throws Exception {
        ObjectNode result = sample();
        ((ObjectNode) result.path("pairs").get(0).path("a")).put("userProductId", "up_12");

        assertThat(RoutineCheckBuilder.build(result, SAMPLE_USING_IDS).isChecked()).isFalse();
    }

    @Test
    void 쌍_개수의_세_값_중_하나라도_없으면_쌍으로_대신_세지_않고_점검_전이다() throws Exception {
        ObjectNode missingAvoid = sample();
        ((ObjectNode) missingAvoid.path("counts")).remove("avoid");
        ObjectNode noCounts = sample();
        noCounts.remove("counts");

        assertThat(RoutineCheckBuilder.build(missingAvoid, SAMPLE_USING_IDS).isChecked()).isFalse();
        assertThat(RoutineCheckBuilder.build(noCounts, SAMPLE_USING_IDS).isChecked()).isFalse();
    }

    @Test
    void 쌍_개수가_실린_쌍_수보다_적으면_점검_전이다() throws Exception {
        for (String count : new String[]{"ok", "separate", "avoid"}) {
            ObjectNode result = sample();
            ((ObjectNode) result.path("counts")).put(count, 0);

            RoutineCheckResponse response = RoutineCheckBuilder.build(result, SAMPLE_USING_IDS);

            assertThat(response.isChecked()).isFalse();
            assertThat(response.getPairs()).isEmpty();
            assertThat(response.getCounts().getAvoid()).isZero();
        }
    }

    @Test
    void 보유_제품이_2개_미만이면_쌍과_개수와_대체_제안을_비우고_사용_순서는_남긴다() throws Exception {
        ObjectNode result = sample();
        result.set("pairs", MAPPER.createArrayNode());
        result.remove("replacement");

        RoutineCheckResponse response = RoutineCheckBuilder.build(result, Set.of(sampleId(1)));

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getProductCount()).isEqualTo(1);
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getCounts().getOk()).isZero();
        assertThat(response.getReplacement()).isNull();
        assertThat(response.getSchedule().getEvening()).hasSize(3);
    }

    @Test
    void 결과가_없거나_쌍_목록이_없으면_점검_전이고_모두_비운다() throws Exception {
        for (JsonNode result : new JsonNode[]{MissingNode.getInstance(),
                MAPPER.readTree("{\"scenario\":\"HOME_ROUTINE\",\"items\":[],\"counts\":{\"ok\":0,\"separate\":0,\"avoid\":0}}")}) {
            RoutineCheckResponse response = RoutineCheckBuilder.build(result, SAMPLE_USING_IDS);

            assertThat(response.isChecked()).isFalse();
            assertThat(response.getProductCount()).isEqualTo(5);
            assertThat(response.getPairs()).isEmpty();
            assertThat(response.getReplacement()).isNull();
            assertThat(response.getSchedule().getMorning()).isEmpty();
            assertThat(response.getUncomparedCount()).isZero();
        }
    }

    @Test
    void 점검했지만_충돌이_없으면_점검은_했고_쌍은_비어_있다() throws Exception {
        RoutineCheckResponse response = RoutineCheckBuilder.build(
                MAPPER.readTree("{\"pairs\":[],\"counts\":{\"ok\":0,\"separate\":0,\"avoid\":0}}"), SAMPLE_USING_IDS);

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getPairs()).isEmpty();
        assertThat(response.getCounts().getAvoid()).isZero();
        assertThat(response.getReplacement()).isNull();
    }

    @Test
    void 궁합을_모르는_쌍은_뺀다() throws Exception {
        ObjectNode result = sample();
        ((ObjectNode) result.path("pairs").get(0)).put("level", "MAYBE");

        assertThat(RoutineCheckBuilder.build(result, SAMPLE_USING_IDS).getPairs()).extracting(Pair::getLevel)
                .containsExactly(CompatibilityLevel.AVOID, CompatibilityLevel.SEPARATE);
    }
}
