package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.CoveredCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.MissingCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.enums.HomeRecommendationState;
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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 홈 맞춤 추천 카드. AI 홈 배치가 하루 한 번 home_recommendations 에 덮어쓴 결과를 읽어 화면 모양으로 바꾼다.
 */
@Service
@RequiredArgsConstructor
public class HomeRecommendationService {

    private final UserRepository userRepository;
    private final HomeResultReader homeResultReader;
    private final UserProductRepository userProductRepository;
    private final ResultAssembler resultAssembler;

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

        Optional<HomeResultReader.Card> found = homeResultReader.find(userId, HomeRecommendationKind.ENV);
        if (found.isEmpty()) {
            return new EnvironmentRecommendationResponse(HomeRecommendationState.NOT_READY, List.of(), List.of(), null, null);
        }
        HomeResultReader.Card card = found.get();
        JsonNode result = card.result();

        List<Condition> conditions = HomeResultReader.conditionsOf(card).orElseGet(List::of);
        RecommendationResultV2Response assembled = resultAssembler.assemble(new ResultAssembler.Source(
                card.jobId(), null, result.path("scenario").asText(null), RecommendationBasis.SELF,
                result, MissingNode.getInstance(), user.getSkinType(), MissingNode.getInstance()), null);
        return new EnvironmentRecommendationResponse(
                assembled.getItems().isEmpty() ? HomeRecommendationState.FULLY_COVERED : HomeRecommendationState.READY,
                conditions.stream().filter(c -> !c.isCovered()).map(c -> new MissingCondition(c.getKey(), c.getLabel())).toList(),
                conditions.stream().filter(Condition::isCovered)
                        .map(c -> new CoveredCondition(c.getKey(), c.getLabel(), c.getCoveredBy())).toList(),
                assembled,
                card.generatedAt());
    }

    /**
     * 쓰는 제품끼리 성분 충돌을 검사한 결과와 대체 추천. 보유 제품 수는 쓰는 중인 보유 제품을 직접 센다.
     * 온보딩의 자주 사용하는 제품은 세지 않는다. 나머지는 AI 홈 루틴 점검 결과에서 꺼내고, 없거나 읽을 수 없으면 점검 전이다.
     * 점검 결과는 하루 한 번 만들어지므로, 그 뒤에 쓰는 제품이 달라졌으면 지난 결과로 보고 점검 전으로 내린다.
     */
    @Transactional(readOnly = true)
    public RoutineCheckResponse getRoutineCheck(UUID userId) {
        Set<UUID> usingIds = new HashSet<>(userProductRepository.findIdsByUserIdAndUsageType(userId, UsageType.USING));
        JsonNode result = homeResultReader.find(userId, HomeRecommendationKind.ROUTINE)
                .map(HomeResultReader.Card::result)
                .orElse(MissingNode.getInstance());
        return RoutineCheckBuilder.build(result, usingIds);
    }
}
