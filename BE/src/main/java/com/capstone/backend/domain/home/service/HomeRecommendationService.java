package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.CoveredCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.MissingCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.enums.HomeRecommendationState;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.service.ResultAssembler;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 홈 맞춤 추천 카드. AI 홈 배치가 하루 한 번 home_recommendations 에 덮어쓴 결과를 읽어 화면 모양으로 바꾼다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HomeRecommendationService {

    private final UserRepository userRepository;
    private final HomeRecommendationRepository homeRecommendationRepository;
    private final UserProductRepository userProductRepository;
    private final ResultAssembler resultAssembler;
    private final JsonUtil jsonUtil;

    /**
     * 비어 있는 환경 조건을 채울 제품 추천. 지역을 설정하지 않았으면 REGION_NOT_SET.
     * 결과가 없거나 읽을 수 없으면 NOT_READY, 권할 제품이 없으면 FULLY_COVERED, 그 외에는 READY 다.
     * 추천 결과는 추천 결과 조회와 같은 모양으로 내린다.
     */
    @Transactional(readOnly = true)
    public EnvironmentRecommendationResponse getEnvironment(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (user.getRegion() == null || user.getRegion().isBlank()) {
            throw new BusinessException(ErrorCode.REGION_NOT_SET);
        }

        Optional<HomeRecommendation> found = homeRecommendationRepository.findById(
                new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV));
        JsonNode result = found.map(row -> readTree(row.getResult(), userId, HomeRecommendationKind.ENV))
                .orElse(MissingNode.getInstance());
        if (found.isEmpty() || !result.isObject()) {
            return new EnvironmentRecommendationResponse(HomeRecommendationState.NOT_READY, List.of(), List.of(), null, null);
        }
        HomeRecommendation row = found.get();

        List<Condition> conditions = EnvConditions.parse(result).orElseGet(List::of);
        RecommendationResultV2Response assembled = resultAssembler.assemble(new ResultAssembler.Source(
                row.getJobId(), null, result.path("scenario").asText(null), RecommendationBasis.SELF,
                result, MissingNode.getInstance(), user.getSkinType(), MissingNode.getInstance()), null);
        return new EnvironmentRecommendationResponse(
                assembled.getItems().isEmpty() ? HomeRecommendationState.FULLY_COVERED : HomeRecommendationState.READY,
                conditions.stream().filter(c -> !c.isCovered()).map(c -> new MissingCondition(c.getKey(), c.getLabel())).toList(),
                conditions.stream().filter(Condition::isCovered)
                        .map(c -> new CoveredCondition(c.getKey(), c.getLabel(), c.getCoveredBy())).toList(),
                assembled,
                row.getGeneratedAt());
    }

    /**
     * 쓰는 제품끼리 성분 충돌을 검사한 결과와 대체 추천. 보유 제품 수는 쓰는 중인 보유 제품을 직접 센다.
     * 온보딩의 자주 사용하는 제품은 세지 않는다. 나머지는 AI 홈 루틴 점검 결과에서 꺼내고, 없거나 읽을 수 없으면 점검 전이다.
     */
    @Transactional(readOnly = true)
    public RoutineCheckResponse getRoutineCheck(UUID userId) {
        int productCount = (int) userProductRepository.countByUserIdAndUsageType(userId, UsageType.USING);
        JsonNode result = homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ROUTINE))
                .map(row -> readTree(row.getResult(), userId, HomeRecommendationKind.ROUTINE))
                .orElse(MissingNode.getInstance());
        return RoutineCheckBuilder.build(result, productCount);
    }

    private JsonNode readTree(String json, UUID userId, HomeRecommendationKind kind) {
        try {
            return jsonUtil.readTree(json);
        } catch (BusinessException e) {
            log.warn("[HomeRecommendation] 홈 추천 결과를 읽지 못해 계산 전으로 본다: userId={}, kind={}", userId, kind, e);
            return MissingNode.getInstance();
        }
    }
}
