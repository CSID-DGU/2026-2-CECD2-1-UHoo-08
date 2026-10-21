package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationRequest;
import com.capstone.backend.domain.recommendation.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationJobResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Clarify;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Step;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.entity.SearchLog;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.repository.SearchLogRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationServiceImpl implements RecommendationService {

    private final RecommendationRepository recommendationRepository;
    private final ProductRepository productRepository;
    private final UserRepository userRepository;
    private final AgentClient agentClient;
    private final ObjectMapper objectMapper;
    private final SearchLogRepository searchLogRepository;
    private final JsonUtil jsonUtil;

    /** 진행 단계 목록이 아직 없을 때(AI 반영 전) 현재 단계 문구 하나로 대신하는 항목의 key */
    static final String CURRENT_STEP_KEY = "current";
    /** AI 결과에 질문이 없을 때 쓰는 질문 제목 */
    static final String DEFAULT_CLARIFY_MESSAGE = "조금만 더 알려주시면 바로 찾아드릴게요";

    @Override
    @Transactional
    public RecommendationJobResponse requestRecommendation(UUID userId, RecommendationRequest request) {
        Product product = productRepository.findById(request.getBaseProductId())
                .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        if (user.getSkinType() == null && user.getPersonalColor() == null) {
            throw new BusinessException(ErrorCode.SKIN_PROFILE_NOT_FOUND);
        }

        int tolerancePercent = request.getPriceTolerancePercent() != null
                ? request.getPriceTolerancePercent() : 10;

        LocalDateTime now = LocalDateTime.now();
        Recommendation job = Recommendation.builder()
                .user(user)
                .product(product)
                .searchPurpose(request.getSearchPurpose())
                .priceTolerancePercent(tolerancePercent)
                .status(JobStatus.PENDING)
                .progress(0)
                .createdAt(now)
                .updatedAt(now)
                .build();

        Recommendation saved = recommendationRepository.save(job);

        Map<String, Object> agentPayload = new HashMap<>();
        agentPayload.put("jobId", saved.getId().toString());
        agentPayload.put("baseProductId", request.getBaseProductId().toString());
        agentPayload.put("userId", userId.toString());
        agentPayload.put("searchPurpose", request.getSearchPurpose());
        agentPayload.put("priceTolerancePercent", tolerancePercent);

        Map<String, Object> userProfile = new HashMap<>();
        userProfile.put("skinType", user.getSkinType());
        userProfile.put("skinConcerns", user.getSkinConcerns() != null
                ? Arrays.asList(user.getSkinConcerns()) : List.of());
        userProfile.put("personalColor", user.getPersonalColor());
        agentPayload.put("userProfile", userProfile);

        agentClient.runAgent(agentPayload);

        return RecommendationJobResponse.of(saved.getId());
    }

    /**
     * 추천 진행 상태. 자연어 추천 job 은 시나리오, 진행 단계, 되묻기를 더해 내리고, 상품 기준 추천 job 은 기존 모양 그대로 내린다.
     * 두 job 은 추천 기준(basis)으로 구분한다. 시나리오는 자연어 추천 job 도 판정 전에는 비어 있어 구분에 쓸 수 없다.
     * job 이 처음 끝난 상태(완료, 실패, 되묻기)가 되면 검색 기록에 해석 결과를 한 번 남긴다.
     */
    @Override
    @Transactional
    public RecommendationStatusResponse getStatus(UUID userId, UUID jobId) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (job.getBasis() == null) {
            return RecommendationStatusResponse.from(job);
        }

        if (job.getStatus().isFinal() || job.getStatus() == JobStatus.NEEDS_CLARIFICATION) {
            recordInterpretation(job);
        }
        Clarify clarify = job.getStatus() == JobStatus.NEEDS_CLARIFICATION ? clarifyOf(job) : null;
        return new RecommendationStatusV2Response(job, stepsOf(job), clarify);
    }

    /** job 의 진행 단계 목록. 아직 없거나 읽을 수 없으면 현재 단계 문구 하나로 대신한다 */
    List<Step> stepsOf(Recommendation job) {
        List<Step> steps = new ArrayList<>();
        JsonNode node = readTreeOrMissing(job.getSteps(), job.getId());
        if (node.isArray()) {
            for (JsonNode step : node) {
                String key = step.path("key").asText(null);
                String label = step.path("label").asText(null);
                String state = step.path("state").asText(null);
                if (key != null && label != null && state != null) {
                    steps.add(new Step(key, label, state));
                }
            }
        }
        if (steps.isEmpty() && job.getStep() != null) {
            steps.add(new Step(CURRENT_STEP_KEY, job.getStep(), "NOW"));
        }
        return steps;
    }

    /** 되묻기 질문은 AI 결과의 clarify.question 이다. 물어볼 항목은 시나리오로 정한다 */
    Clarify clarifyOf(Recommendation job) {
        String question = readTreeOrMissing(job.getResult(), job.getId()).path("clarify").path("question").asText(null);
        String message = question == null || question.isBlank() ? DEFAULT_CLARIFY_MESSAGE : question;
        return new Clarify(message, ClarifyFieldMapper.map(job.getScenario(), null));
    }

    private void recordInterpretation(Recommendation job) {
        Float confidence = null;
        JsonNode spec = readTreeOrMissing(job.getQuerySpec(), job.getId());
        if (spec.path("confidence").isNumber()) {
            confidence = spec.path("confidence").floatValue();
        }
        for (SearchLog searchLog : searchLogRepository.findByJobId(job.getId())) {
            if (searchLog.isInterpretationEmpty()) {
                searchLog.recordInterpretation(job.getScenario(), job.getQuerySpec(), confidence);
            }
        }
    }

    // 상태 조회는 화면이 계속 폴링하므로, AI 가 쓴 값 하나가 깨져도 조회 자체는 실패시키지 않는다
    private JsonNode readTreeOrMissing(String json, UUID jobId) {
        try {
            return jsonUtil.readTree(json);
        } catch (BusinessException e) {
            log.warn("[RecommendationStatus] job 의 jsonb 를 읽지 못해 비어 있는 것으로 본다: jobId={}", jobId);
            return MissingNode.getInstance();
        }
    }

    @Override
    @Transactional(readOnly = true)
    public RecommendationResultResponse getResult(UUID userId, UUID jobId) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        if (job.getStatus() != JobStatus.COMPLETED) {
            throw new BusinessException(ErrorCode.JOB_NOT_COMPLETED);
        }

        Product baseProduct = job.getProduct();
        Map<String, Object> resultMap = parseResult(job.getResult());

        Integer matchScore = toInt(resultMap.get("matchScore"));
        String matchLabel = (String) resultMap.get("matchLabel");
        String aiReason = (String) resultMap.get("aiReason");

        List<RecommendationResultResponse.MainRecommendation> mainRecommendations =
                parseMainRecommendations(resultMap.get("mainRecommendations"));
        List<RecommendationResultResponse.SimilarProduct> similarProducts = parseProducts(
                resultMap.get("similarUserProducts"), "satisfactionPercent");
        List<RecommendationResultResponse.AlternativeProduct> alternativeProducts =
                parseAlternativeProducts(resultMap.get("alternativeProducts"));

        return RecommendationResultResponse.builder()
                .jobId(job.getId())
                // 조건 탐색처럼 기준 상품 없이 시작한 job 은 비어 있다.
                .baseProduct(baseProduct == null ? null
                        : RecommendationResultResponse.BaseProductInfo.builder()
                        .id(baseProduct.getId())
                        .name(baseProduct.getName())
                        .brand(baseProduct.getBrand())
                        .imageUrl(baseProduct.getImageUrl())
                        .build())
                .matchScore(matchScore)
                .matchLabel(matchLabel)
                .aiReason(aiReason)
                .mainRecommendations(mainRecommendations)
                .similarUserProducts(similarProducts)
                .alternativeProducts(alternativeProducts)
                .createdAt(job.getCreatedAt())
                .build();
    }

    private Map<String, Object> parseResult(String resultJson) {
        if (resultJson == null) return Map.of();
        try {
            return objectMapper.readValue(resultJson, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.warn("Failed to parse recommendation result JSON: {}", e.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.MainRecommendation> parseMainRecommendations(Object raw) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> {
                    Map<String, Object> bd = (Map<String, Object>) m.get("breakdown");
                    RecommendationResultResponse.ScoreBreakdown breakdown = null;
                    if (bd != null) {
                        breakdown = RecommendationResultResponse.ScoreBreakdown.builder()
                                .budgetFit(toInt(bd.get("budgetFit")))
                                .priceValue(toInt(bd.get("priceValue")))
                                .reviewScore(toInt(bd.get("reviewScore")))
                                .personalization(toInt(bd.get("personalization")))
                                .build();
                    }
                    return RecommendationResultResponse.MainRecommendation.builder()
                            .id(parseUUID(m.get("productId")))
                            .name((String) m.get("name"))
                            .brand((String) m.get("brand"))
                            .imageUrl((String) m.get("imageUrl"))
                            .price(toInt(m.get("price")))
                            .totalScore(toInt(m.get("totalScore")))
                            .breakdown(breakdown)
                            .build();
                })
                .collect(Collectors.toList());
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.SimilarProduct> parseProducts(Object raw, String percentKey) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> RecommendationResultResponse.SimilarProduct.builder()
                        .id(parseUUID(m.get("id")))
                        .name((String) m.get("name"))
                        .brand((String) m.get("brand"))
                        .imageUrl((String) m.get("imageUrl"))
                        .price(toInt(m.get("price")))
                        .satisfactionPercent(toInt(m.get(percentKey)))
                        .build())
                .collect(Collectors.toList());
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.AlternativeProduct> parseAlternativeProducts(Object raw) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> RecommendationResultResponse.AlternativeProduct.builder()
                        .id(parseUUID(m.get("id")))
                        .name((String) m.get("name"))
                        .brand((String) m.get("brand"))
                        .imageUrl((String) m.get("imageUrl"))
                        .price(toInt(m.get("price")))
                        .ingredientSimilarity(toDouble(m.get("ingredientSimilarity")))
                        .build())
                .collect(Collectors.toList());
    }

    private Integer toInt(Object o) {
        if (o == null) return null;
        if (o instanceof Number) return ((Number) o).intValue();
        return null;
    }

    private Double toDouble(Object o) {
        if (o == null) return null;
        if (o instanceof Number) return ((Number) o).doubleValue();
        return null;
    }

    @Override
    public ProductSearchResponse searchProducts(UUID userId, String query) {
        return agentClient.searchProducts(query, userId != null ? userId.toString() : null);
    }

    private UUID parseUUID(Object o) {
        if (o == null) return null;
        try { return UUID.fromString(o.toString()); } catch (Exception e) { return null; }
    }
}
