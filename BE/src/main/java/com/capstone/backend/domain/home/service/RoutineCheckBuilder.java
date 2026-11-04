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
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * AI 홈 루틴 점검 결과의 점검 블록(counts, pairs, replacement, schedule, uncomparedCount, checkedUserProductIds)을 화면 모양으로 바꾼다.
 *
 * 다음이면 점검 전으로 보고 모두 비운다. 빈 값이나 지난 값을 내리면 충돌이 없거나 지금 제품의 결과인 것처럼 보인다.
 *   결과에 쌍 목록(pairs)이 없다
 *   쌍 개수(counts)의 세 값 중 하나라도 없다. 쌍 목록은 일부만 실릴 수 있어 쌍으로 개수를 대신 세지 않는다
 *   쌍 개수가 궁합별로 실린 쌍 수보다 적다. 개수만 보는 배너와 쌍으로 만드는 문구가 어긋난다
 *   점검한 보유 제품 목록(checkedUserProductIds)이 없거나 지금 쓰는 중인 제품과 다르다. 점검 뒤에 제품을 추가하거나, 되돌리거나, 다 쓰거나, 지웠다
 *   쌍이나 대체 제안이 가리키는 보유 제품이 지금 쓰는 중인 제품이 아니다
 * 보유 제품이 2개 미만이면 비교할 쌍이 없으므로 쌍 목록, 쌍 개수, 대체 제안을 비운다. 사용 순서는 제품 하나여도 남긴다.
 */
public final class RoutineCheckBuilder {

    /** 쌍을 만들 수 있는 최소 보유 제품 수 */
    static final int MIN_PAIR_PRODUCTS = 2;

    private RoutineCheckBuilder() {
    }

    /**
     * @param result   AI 홈 루틴 점검 결과. 없으면 MissingNode
     * @param usingIds 쓰는 중인 보유 제품 id. 개수가 보유 제품 수다
     */
    public static RoutineCheckResponse build(JsonNode result, Set<UUID> usingIds) {
        int productCount = usingIds.size();
        Counts counts = counts(result.path("counts"));
        if (!result.path("pairs").isArray() || counts == null || !coversPairs(counts, result.path("pairs"))
                || !checkedSame(result.path("checkedUserProductIds"), usingIds) || !referencesOnly(result, usingIds)) {
            return new RoutineCheckResponse(false, productCount, new Counts(0, 0, 0), List.of(), null, emptySchedule(), 0);
        }
        Schedule schedule = schedule(result.path("schedule"));
        int uncomparedCount = result.path("uncomparedCount").asInt(0);
        if (productCount < MIN_PAIR_PRODUCTS) {
            return new RoutineCheckResponse(true, productCount, new Counts(0, 0, 0), List.of(), null, schedule,
                    uncomparedCount);
        }
        List<Pair> pairs = pairs(result.path("pairs"));
        return new RoutineCheckResponse(true, productCount, counts, pairs,
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

    /** 세 값이 모두 숫자일 때만 쓴다. 하나라도 없으면 null */
    private static Counts counts(JsonNode node) {
        JsonNode ok = node.path("ok");
        JsonNode separate = node.path("separate");
        JsonNode avoid = node.path("avoid");
        if (!ok.isIntegralNumber() || !separate.isIntegralNumber() || !avoid.isIntegralNumber()) {
            return null;
        }
        return new Counts(ok.asInt(), separate.asInt(), avoid.asInt());
    }

    /** 궁합별 개수가 실린 쌍 수 이상인지 */
    private static boolean coversPairs(Counts counts, JsonNode pairs) {
        return counts.getOk() >= pairCount(pairs, CompatibilityLevel.OK)
                && counts.getSeparate() >= pairCount(pairs, CompatibilityLevel.SEPARATE)
                && counts.getAvoid() >= pairCount(pairs, CompatibilityLevel.AVOID);
    }

    private static int pairCount(JsonNode pairs, CompatibilityLevel level) {
        int count = 0;
        for (JsonNode pair : pairs) {
            if (level.name().equals(pair.path("level").asText())) {
                count++;
            }
        }
        return count;
    }

    /** 점검한 보유 제품이 지금 쓰는 중인 보유 제품과 같은지. 목록이 없거나 id 형식이 틀리면 같다고 볼 수 없다 */
    private static boolean checkedSame(JsonNode checkedIds, Set<UUID> usingIds) {
        if (!checkedIds.isArray()) {
            return false;
        }
        Set<UUID> checked = new HashSet<>();
        try {
            checkedIds.forEach(id -> checked.add(UUID.fromString(id.asText(""))));
        } catch (IllegalArgumentException e) {
            return false;
        }
        return checked.equals(usingIds);
    }

    /** 쌍의 두 제품과 대체 제안의 바꿀 제품이 모두 지금 쓰는 중인 보유 제품인지 */
    private static boolean referencesOnly(JsonNode result, Set<UUID> usingIds) {
        List<JsonNode> refs = new ArrayList<>();
        result.path("pairs").forEach(pair -> {
            refs.add(pair.path("a"));
            refs.add(pair.path("b"));
        });
        if (result.path("replacement").isObject()) {
            refs.add(result.path("replacement").path("replaceTarget"));
        }
        return refs.stream().allMatch(ref -> {
            try {
                return usingIds.contains(UUID.fromString(ref.path("userProductId").asText("")));
            } catch (IllegalArgumentException e) {
                return false;
            }
        });
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
