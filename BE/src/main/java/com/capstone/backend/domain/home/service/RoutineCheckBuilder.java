package com.capstone.backend.domain.home.service;

import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Counts;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Pair;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Replacement;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.ReplacementItem;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Schedule;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.UserProductRef;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * AI 홈 루틴 점검 결과의 점검 블록(counts, pairs, replacement, schedule, uncomparedCount)을 화면 모양으로 바꾼다.
 *
 * 결과에 쌍 목록(pairs)이 없으면 아직 점검 전으로 보고 모두 비운다. 빈 값으로 내리면 충돌이 없는 것처럼 보인다.
 * 보유 제품이 2개 미만이면 비교할 쌍이 없으므로 쌍 목록, 쌍 개수, 대체 제안을 비운다. 사용 순서는 제품 하나여도 남긴다.
 */
public final class RoutineCheckBuilder {

    /** 쌍을 만들 수 있는 최소 보유 제품 수 */
    static final int MIN_PAIR_PRODUCTS = 2;

    private RoutineCheckBuilder() {
    }

    /**
     * @param result       AI 홈 루틴 점검 결과. 없으면 MissingNode
     * @param productCount 쓰는 중인 보유 제품 수
     */
    public static RoutineCheckResponse build(JsonNode result, int productCount) {
        if (!result.path("pairs").isArray()) {
            return new RoutineCheckResponse(false, productCount, new Counts(0, 0, 0), List.of(), null, emptySchedule(), 0);
        }
        Schedule schedule = schedule(result.path("schedule"));
        int uncomparedCount = result.path("uncomparedCount").asInt(0);
        if (productCount < MIN_PAIR_PRODUCTS) {
            return new RoutineCheckResponse(true, productCount, new Counts(0, 0, 0), List.of(), null, schedule,
                    uncomparedCount);
        }
        List<Pair> pairs = pairs(result.path("pairs"));
        return new RoutineCheckResponse(true, productCount, counts(result.path("counts"), pairs), pairs,
                replacement(result.path("replacement")), schedule, uncomparedCount);
    }

    /** 궁합 순서로 정렬한다. 궁합 값을 모르는 쌍은 어디에 둘지 알 수 없어 뺀다 */
    private static List<Pair> pairs(JsonNode array) {
        List<Pair> pairs = new ArrayList<>();
        array.forEach(node -> {
            CompatibilityLevel level = levelOf(node.path("level").asText(""));
            if (level != null) {
                pairs.add(new Pair(ref(node.path("a")), ref(node.path("b")), level,
                        node.path("title").asText(null), node.path("reason").asText(null)));
            }
        });
        pairs.sort(Comparator.comparing(Pair::getLevel));
        return pairs;
    }

    /** 결과에 개수가 없으면 쌍 목록에서 센다 */
    private static Counts counts(JsonNode node, List<Pair> pairs) {
        if (node.isObject()) {
            return new Counts(node.path("ok").asInt(0), node.path("separate").asInt(0), node.path("avoid").asInt(0));
        }
        return new Counts(count(pairs, CompatibilityLevel.OK), count(pairs, CompatibilityLevel.SEPARATE),
                count(pairs, CompatibilityLevel.AVOID));
    }

    private static int count(List<Pair> pairs, CompatibilityLevel level) {
        return (int) pairs.stream().filter(pair -> pair.getLevel() == level).count();
    }

    private static Replacement replacement(JsonNode node) {
        if (!node.isObject()) {
            return null;
        }
        List<ReplacementItem> items = new ArrayList<>();
        node.path("items").forEach(item -> items.add(new ReplacementItem(
                item.path("productId").asText(null), item.path("name").asText(null), item.path("brand").asText(null),
                intOrNull(item.path("price")), intOrNull(item.path("totalScore")), item.path("badge").asText(null))));
        return new Replacement(ref(node.path("replaceTarget")), node.path("message").asText(null), items);
    }

    private static Schedule schedule(JsonNode node) {
        return new Schedule(texts(node.path("morning")), texts(node.path("evening")), node.path("tip").asText(null));
    }

    private static Schedule emptySchedule() {
        return new Schedule(List.of(), List.of(), null);
    }

    private static UserProductRef ref(JsonNode node) {
        return new UserProductRef(node.path("userProductId").asText(null), node.path("name").asText(null));
    }

    private static CompatibilityLevel levelOf(String value) {
        try {
            return CompatibilityLevel.valueOf(value);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static Integer intOrNull(JsonNode node) {
        return node.isNumber() ? node.asInt() : null;
    }

    private static List<String> texts(JsonNode array) {
        List<String> values = new ArrayList<>();
        array.forEach(node -> {
            if (node.isTextual() && !node.asText().isBlank()) {
                values.add(node.asText());
            }
        });
        return values;
    }
}
