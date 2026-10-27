package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Alternative;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.AppliedPreference;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Badge;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Bundle;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Excluded;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.ExcludedItem;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Item;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.ScoreItem;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.SimilarUserProduct;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Slot;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * AI 추천 결과(AI/contracts/result.py 의 RecommendationResult)를 FE 명세 모양으로 조립한다. AI 계약은 건드리지 않는다.
 *
 * 필드 이름이 같은 값은 그대로 옮기고, 모양이 다른 곳만 바꾼다.
 * 가격이 비어 있으면 상품의 정가로, 인기 기준이면 평점과 리뷰 수를 상품 정보에서 채운다.
 * 추천 결과 조회와 홈 환경 추천이 함께 쓴다.
 */
@Component
@RequiredArgsConstructor
public class ResultAssembler {

    /** 대체 후보의 점수 분해에서 유사도를 담는 항목 키 */
    static final String SIMILARITY_KEY = "similarity";

    private final ProductRepository productRepository;

    /**
     * 조립에 필요한 값.
     *
     * @param result        AI 결과(jsonb)
     * @param stateSnapshot job 의 그래프 상태(jsonb). 대체 후보를 뺀 수를 읽는다. 없으면 MissingNode
     * @param userSkinType  내 피부 기준 문구에 쓰는 users.skin_type
     * @param targetProfile 다른 사람 기준 문구에 쓰는 job 의 target_profile. 없으면 MissingNode
     */
    public record Source(UUID jobId, UUID parentJobId, String scenario, RecommendationBasis basis,
                         JsonNode result, JsonNode stateSnapshot, String userSkinType, JsonNode targetProfile) {
    }

    public RecommendationResultV2Response assemble(Source source, AppliedPreference appliedPreference) {
        List<UUID> productIds = productIdsOf(source.result());
        Map<String, Product> products = productIds.isEmpty() ? Map.of()
                : productRepository.findAllById(productIds).stream()
                .collect(Collectors.toMap(p -> p.getId().toString(), Function.identity()));
        return assemble(source, products, appliedPreference);
    }

    static RecommendationResultV2Response assemble(Source source, Map<String, Product> products,
                                                   AppliedPreference appliedPreference) {
        JsonNode result = source.result();
        JsonNode query = result.path("query");
        boolean popular = source.basis() == RecommendationBasis.POPULAR;

        List<Item> items = new ArrayList<>();
        result.path("items").forEach(node -> items.add(item(node, products, popular)));

        String scenario = source.scenario() != null ? source.scenario() : result.path("scenario").asText(null);
        return new RecommendationResultV2Response(
                source.jobId(),
                source.parentJobId(),
                scenario,
                source.basis(),
                SummaryBuilder.build(query, items.size(), source.basis(), source.userSkinType(), source.targetProfile()),
                appliedPreference,
                items,
                excluded(result.path("excluded")),
                alternatives(result.path("alternatives"), products),
                droppedCount(source.stateSnapshot()),
                similarUserProducts(result.path("similarUserProducts"), products),
                bundles(result.path("bundles"), query, products));
    }

    static Item item(JsonNode node, Map<String, Product> products, boolean popular) {
        String productId = node.path("productId").asText(null);
        Product product = products.get(productId);

        List<ScoreItem> breakdown = new ArrayList<>();
        node.path("breakdown").forEach(score -> breakdown.add(new ScoreItem(
                score.path("key").asText(null), score.path("label").asText(null),
                doubleOrNull(score.path("score")), doubleOrNull(score.path("weight")))));
        List<Badge> badges = new ArrayList<>();
        node.path("badges").forEach(badge -> badges.add(new Badge(
                badge.path("type").asText(null), badge.path("text").asText(null))));

        return new Item(
                productId,
                node.path("name").asText(null),
                node.path("brand").asText(null),
                node.path("imageUrl").asText(null),
                price(node, product),
                // 인기 기준은 점수가 아니라 평점과 리뷰 수로 보여 준다
                popular ? null : intOrNull(node.path("totalScore")),
                popular && product != null && product.getAverageScore() != null ? product.getAverageScore().doubleValue() : null,
                popular && product != null ? product.getReviewCount() : null,
                breakdown,
                badges,
                node.path("reason").asText(null),
                node.path("change").asText(null),
                intOrNull(node.path("rankDelta")));
    }

    static Excluded excluded(JsonNode array) {
        List<ExcludedItem> items = new ArrayList<>();
        array.forEach(node -> items.add(new ExcludedItem(
                node.path("productId").asText(null), node.path("name").asText(null),
                node.path("reason").asText(null), node.path("detail").asText(null))));
        return new Excluded(items.size(), items);
    }

    static List<Alternative> alternatives(JsonNode array, Map<String, Product> products) {
        List<Alternative> alternatives = new ArrayList<>();
        array.forEach(node -> alternatives.add(new Alternative(
                node.path("productId").asText(null), node.path("name").asText(null), node.path("brand").asText(null),
                price(node, products.get(node.path("productId").asText(null))),
                similarity(node.path("breakdown")),
                intOrNull(node.path("totalScore")))));
        return alternatives;
    }

    static List<SimilarUserProduct> similarUserProducts(JsonNode array, Map<String, Product> products) {
        List<SimilarUserProduct> similar = new ArrayList<>();
        array.forEach(node -> similar.add(new SimilarUserProduct(
                node.path("productId").asText(null), node.path("name").asText(null), node.path("brand").asText(null),
                price(node, products.get(node.path("productId").asText(null))))));
        return similar;
    }

    /**
     * 예산 세트 조합. AI 의 BundleOption 에는 칸 정보가 아직 없어, 칸 키는 칸 순서로 두고 칸 이름과 조합 유형은 비워 둔다.
     */
    static List<Bundle> bundles(JsonNode array, JsonNode query, Map<String, Product> products) {
        Integer budget = intOrNull(query.path("budgetTotal"));
        List<Bundle> bundles = new ArrayList<>();
        int index = 1;
        for (JsonNode node : array) {
            int total = node.path("totalPrice").asInt(0);
            List<Slot> slots = new ArrayList<>();
            int totalScore = 0;
            int slot = 0;
            for (JsonNode item : node.path("items")) {
                Integer score = intOrNull(item.path("totalScore"));
                totalScore += score == null ? 0 : score;
                slots.add(new Slot(String.valueOf(slot++), null, item.path("productId").asText(null),
                        item.path("name").asText(null), price(item, products.get(item.path("productId").asText(null))),
                        score));
            }
            bundles.add(new Bundle(index++, null, node.path("label").asText(null), total,
                    budget == null ? null : budget - total, totalScore, slots));
        }
        return bundles;
    }

    /** AI 가 가격을 비워 두면 상품의 정가로 채운다 */
    static Integer price(JsonNode node, Product product) {
        Integer price = intOrNull(node.path("price"));
        if (price != null) {
            return price;
        }
        return product == null ? null : product.getOriginalPrice();
    }

    static Double similarity(JsonNode breakdown) {
        for (JsonNode score : breakdown) {
            if (SIMILARITY_KEY.equals(score.path("key").asText(null))) {
                return doubleOrNull(score.path("score"));
            }
        }
        return null;
    }

    /** 대체 후보를 점수 기준으로 뺀 수. AI 가 상태에 남기기 전까지는 0 */
    static int droppedCount(JsonNode stateSnapshot) {
        JsonNode count = stateSnapshot.path("alternativesDroppedCount");
        if (count.isMissingNode()) {
            count = stateSnapshot.path("alternatives_dropped_count");
        }
        return count.asInt(0);
    }

    /** 결과에 나오는 모든 상품 ID. 가격과 평점을 한 번에 채우려고 모은다 */
    static List<UUID> productIdsOf(JsonNode result) {
        Set<UUID> ids = new LinkedHashSet<>();
        for (String field : List.of("items", "alternatives", "similarUserProducts")) {
            result.path(field).forEach(node -> addId(ids, node));
        }
        result.path("bundles").forEach(bundle -> bundle.path("items").forEach(node -> addId(ids, node)));
        return new ArrayList<>(ids);
    }

    private static void addId(Set<UUID> ids, JsonNode node) {
        try {
            ids.add(UUID.fromString(node.path("productId").asText("")));
        } catch (IllegalArgumentException ignored) {
            // 상품 ID 가 아니면 상품 정보로 채우지 않고 AI 값만 쓴다
        }
    }

    private static Integer intOrNull(JsonNode node) {
        return node.isNumber() ? node.intValue() : null;
    }

    private static Double doubleOrNull(JsonNode node) {
        return node.isNumber() ? node.doubleValue() : null;
    }
}
