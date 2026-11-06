package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.request.FeedbackRequest;
import com.capstone.backend.domain.recommendation.dto.response.FeedbackResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.FeedbackReason;
import com.capstone.backend.domain.recommendation.enums.FeedbackVote;
import com.capstone.backend.domain.recommendation.repository.RecommendationFeedbackRepository;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 추천 결과 카드의 좋아요/별로예요.
 *
 * BE 는 반응을 저장하고 AI 에 가중치를 다시 계산하라고 알리기만 한다. 반응을 가중치로 바꾸는 규칙은 AI 에 있다.
 * 가중치는 비동기로 바뀌므로 응답에 되돌리기 ID 는 싣지 않는다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationFeedbackService {

    private final RecommendationRepository recommendationRepository;
    private final RecommendationFeedbackRepository feedbackRepository;
    private final RecommendationJobService recommendationJobService;
    private final JsonUtil jsonUtil;

    /**
     * 내 job 결과의 추천 목록에 있는 제품에만 피드백을 남긴다. 목록에 없는 제품이면 VALIDATION_ERROR.
     * 같은 job 의 같은 제품에 다시 보내면 덮어쓴다. 이유는 별로예요일 때만 저장한다.
     */
    @Transactional
    public FeedbackResponse submit(UUID userId, UUID jobId, FeedbackRequest request) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (!resultProductIds(job).contains(request.getProductId())) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }

        FeedbackVote vote = request.getVote();
        Long feedbackId = feedbackRepository.upsert(jobId, userId, request.getProductId(), vote.name(),
                reasonTagsOf(vote, request.getReasonTags()));
        recommendationJobService.requestFeedbackApply(userId);
        return new FeedbackResponse(String.valueOf(feedbackId), vote.message(), null);
    }

    /** 저장할 이유를 PostgreSQL 배열 문자열로 만든다. 좋아요면 비우고, 겹친 이유는 한 번만 이유 목록 순서로 둔다 */
    static String reasonTagsOf(FeedbackVote vote, List<FeedbackReason> reasons) {
        EnumSet<FeedbackReason> distinct = EnumSet.noneOf(FeedbackReason.class);
        if (vote == FeedbackVote.DOWN && reasons != null) {
            reasons.stream().filter(Objects::nonNull).forEach(distinct::add);
        }
        return distinct.stream().map(FeedbackReason::name).collect(Collectors.joining(",", "{", "}"));
    }

    /** 결과 추천 목록의 상품 ID. 결과가 없거나 읽을 수 없으면 빈 목록 */
    private Set<UUID> resultProductIds(Recommendation job) {
        JsonNode items;
        try {
            items = jsonUtil.readTree(job.getResult()).path("items");
        } catch (BusinessException e) {
            log.warn("[RecommendationFeedback] job 의 결과를 읽지 못해 추천 목록을 비어 있는 것으로 본다: jobId={}", job.getId());
            return Set.of();
        }
        Set<UUID> productIds = new HashSet<>();
        items.forEach(item -> {
            try {
                productIds.add(UUID.fromString(item.path("productId").asText("")));
            } catch (IllegalArgumentException ignored) {
                // 상품 ID 가 없거나 형식이 틀린 카드는 피드백 대상이 아니다
            }
        });
        return productIds;
    }
}
