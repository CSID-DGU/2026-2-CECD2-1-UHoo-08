package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * AI 홈 배치가 home_recommendations 에 쓴 결과를 읽는다. 환경 요약, 환경 기반 추천, 루틴 점검이 함께 쓴다.
 *
 * 행이 없거나 결과를 읽을 수 없으면 카드가 없는 것으로 본다. 빈 값으로 내리면 분석했는데 해당 항목이 없는 것처럼 보인다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class HomeResultReader {

    private final HomeRecommendationRepository homeRecommendationRepository;
    private final JsonUtil jsonUtil;

    /** 읽어 낸 홈 카드. result 는 항상 객체다 */
    public record Card(UUID jobId, OffsetDateTime generatedAt, JsonNode result) {
    }

    public Optional<Card> find(UUID userId, HomeRecommendationKind kind) {
        return homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, kind))
                .flatMap(row -> toCard(row, userId, kind));
    }

    private Optional<Card> toCard(HomeRecommendation row, UUID userId, HomeRecommendationKind kind) {
        JsonNode result;
        try {
            result = jsonUtil.readTree(row.getResult());
        } catch (BusinessException e) {
            log.warn("[HomeResult] 홈 추천 결과를 읽지 못해 없는 것으로 본다: userId={}, kind={}", userId, kind, e);
            return Optional.empty();
        }
        return result.isObject() ? Optional.of(new Card(row.getJobId(), row.getGeneratedAt(), result)) : Optional.empty();
    }

    /**
     * 환경 카드의 조건 블록(conditions[{key,label,basis,covered,coveredBy}]).
     * 조건 블록을 싣기 전의 결과는 행이 있어도 분석 전으로 보고 비어 있다. key 가 없는 항목은 건너뛴다.
     */
    public static Optional<List<Condition>> conditionsOf(Card card) {
        JsonNode items = card.result().path("conditions");
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
