package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Summary;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.RecommendationCategory;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 추천 결과 상단 문구. AI 결과의 query 요약과 추천 기준으로 만든다.
 *
 * 기준 문구는 내 피부면 피부 타입과 맨 앞 조건 하나, 인기면 기간, 다른 사람이면 관계와 피부 타입으로 만든다.
 * 조건 칩은 AI 가 사람이 읽는 문장으로 합친 조건에 예산 문구를 더한다.
 */
public final class SummaryBuilder {

    static final String POPULAR_BASIS = "최근 30일 기준";
    static final String SELF_FALLBACK = "내 피부 기준";
    static final String OTHER_FALLBACK = "다른 분 기준";
    static final String VALUE_NOTICE = "가격 대비 효능과 후기를 함께 보고 골랐어요";
    static final String ENV_NOTICE = "요즘 지내시는 곳의 날씨와 공기를 함께 반영했어요";
    /** 기준 문구에 넣는 조건 수. 오른쪽 위 작은 자리라 하나만 넣는다 */
    static final int BASIS_CONDITIONS = 1;

    private static final Map<String, String> SKIN_TYPES = Map.of(
            "DRY", "건성",
            "OILY", "지성",
            "NORMAL", "중성",
            "COMBINATION", "복합성",
            "OILY_DEHYDRATED", "수분 부족 지성",
            "DEHYDRATED_OILY", "수분 부족 지성"
    );

    private static final Map<String, String> RELATIONS = Map.of(
            "MOM", "엄마",
            "DAD", "아빠",
            "CHILD", "아이",
            "FRIEND", "친구",
            "GIFT", "선물"
    );

    private SummaryBuilder() {
    }

    /**
     * @param query         AI 결과의 query 요약(QuerySummary). 없으면 MissingNode
     * @param totalCount    추천 목록 수
     * @param userSkinType  users.skin_type. 내 피부 기준에서만 쓴다
     * @param targetProfile job 의 target_profile. 다른 사람 기준에서만 쓴다
     */
    public static Summary build(JsonNode query, int totalCount, RecommendationBasis basis,
                                String userSkinType, JsonNode targetProfile) {
        List<String> queryConditions = texts(query.path("conditions"));
        return new Summary(
                RecommendationCategory.labelOf(query.path("category").asText(null)),
                totalCount,
                basisLabel(basis, queryConditions, userSkinType, targetProfile),
                conditions(query, queryConditions),
                notice(query));
    }

    /** 조건 칩. AI 조건 뒤에 예산 문구를 붙인다. 조건 추가 선택지 화면의 현재 조건과 같은 값이다 */
    public static List<String> conditions(JsonNode query) {
        return conditions(query, texts(query.path("conditions")));
    }

    private static List<String> conditions(JsonNode query, List<String> queryConditions) {
        List<String> conditions = new ArrayList<>(queryConditions);
        if (query.path("budgetMax").isIntegralNumber()) {
            conditions.add(won(query.path("budgetMax").asLong()) + " 이하");
        }
        if (query.path("budgetTotal").isIntegralNumber()) {
            conditions.add("총 " + won(query.path("budgetTotal").asLong()));
        }
        return conditions;
    }

    static String basisLabel(RecommendationBasis basis, List<String> conditions, String userSkinType,
                             JsonNode targetProfile) {
        if (basis == RecommendationBasis.POPULAR) {
            return POPULAR_BASIS;
        }
        List<String> parts = new ArrayList<>();
        if (basis == RecommendationBasis.OTHER) {
            addIfPresent(parts, RELATIONS.get(targetProfile.path("relation").asText("")));
            addIfPresent(parts, SKIN_TYPES.get(targetProfile.path("skinType").asText("")));
            return parts.isEmpty() ? OTHER_FALLBACK : String.join(" · ", parts) + " 기준";
        }
        addIfPresent(parts, userSkinType == null ? null : SKIN_TYPES.get(userSkinType));
        conditions.stream().limit(BASIS_CONDITIONS).forEach(parts::add);
        return parts.isEmpty() ? SELF_FALLBACK : String.join(" · ", parts) + " 기준";
    }

    static String notice(JsonNode query) {
        if (query.path("valueSeeking").asBoolean(false)) {
            return VALUE_NOTICE;
        }
        if (query.path("useEnv").asBoolean(false)) {
            return ENV_NOTICE;
        }
        return null;
    }

    /** 30000 → "3만원", 35000 → "3.5만원", 12345 → "12,345원" */
    static String won(long amount) {
        if (amount >= 10000 && amount % 1000 == 0) {
            long thousands = amount / 1000;
            return thousands % 10 == 0 ? (thousands / 10) + "만원" : (thousands / 10) + "." + (thousands % 10) + "만원";
        }
        return String.format("%,d원", amount);
    }

    private static List<String> texts(JsonNode array) {
        List<String> values = new ArrayList<>();
        if (array.isArray()) {
            array.forEach(node -> {
                if (node.isTextual() && !node.asText().isBlank()) {
                    values.add(node.asText());
                }
            });
        }
        return values;
    }

    private static void addIfPresent(List<String> parts, String value) {
        if (value != null) {
            parts.add(value);
        }
    }
}
