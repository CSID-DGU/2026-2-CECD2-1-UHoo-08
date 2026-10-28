package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentClarifyRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentRunV2Request;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.request.ClarificationRequest;
import com.capstone.backend.domain.recommendation.dto.request.ClarificationRequest.Answers;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.response.ClarificationResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.entity.SearchLog;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.repository.SearchLogRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * 추천 job 을 만들고 AI 추천 실행을 맡긴다. 자연어 추천 요청과 조건 수정(재탐색)이 함께 쓰고, 되묻기 답도 여기서 AI 에 넘긴다.
 *
 * AI 는 job 행을 읽고 갱신하므로, job 이 커밋된 뒤에 호출한다. 커밋 전에 부르면 AI 가 아직 없는 job 을 찾게 된다.
 * AI 호출은 비동기이고 실패해도 요청은 접수된 것으로 둔다. 실패한 job 은 진행되지 않는 것으로 드러나고 정리 배치가 실패로 바꾼다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationJobService {

    static final int ESTIMATED_SECONDS = 8;

    private final RecommendationRepository recommendationRepository;
    private final SearchLogRepository searchLogRepository;
    private final UserRepository userRepository;
    private final AiInternalClient aiInternalClient;
    private final JsonUtil jsonUtil;
    private final ProductRepository productRepository;

    /** 검색창 문장으로 추천을 요청한다. 내 피부 기준인데 피부 정보가 없으면 SKIN_PROFILE_NOT_FOUND */
    @Transactional
    public RecommendationQueryResponse requestQuery(UUID userId, RecommendationQueryRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        RecommendationBasis basis = request.basisOrDefault();
        if (basis == RecommendationBasis.SELF && (user.getSkinType() == null || user.getSkinType().isBlank())) {
            throw new BusinessException(ErrorCode.SKIN_PROFILE_NOT_FOUND);
        }
        // 쓰실 분 정보는 다른 사람 기준일 때만 의미가 있다
        String targetProfile = basis == RecommendationBasis.OTHER ? jsonUtil.write(request.getTargetProfile()) : null;

        Recommendation job = startJob(user, request.getQuery().strip(), basis, targetProfile, null);
        return new RecommendationQueryResponse(job.getId(), ESTIMATED_SECONDS,
                "/recommendations/" + job.getId() + "/status");
    }

    /**
     * 되묻는 중인 job 에 사용자의 답을 넘겨 같은 job 을 이어서 돌린다. 되묻는 중이 아니면 CLARIFY_NOT_REQUIRED.
     *
     * job 상태는 여기서 바꾸지 않는다. AI 는 job 이 아직 되묻는 중일 때만 답을 받아 이어 돌리고 그때 진행 중으로 바꾼다.
     * 먼저 진행 중으로 바꾸면 AI 가 답을 무시한다. 응답은 곧 진행될 상태(IN_PROGRESS)로 내린다.
     */
    @Transactional
    public ClarificationResponse answerClarification(UUID userId, UUID jobId, ClarificationRequest request) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (job.getStatus() != JobStatus.NEEDS_CLARIFICATION) {
            throw new BusinessException(ErrorCode.CLARIFY_NOT_REQUIRED);
        }

        Answers answers = request.getAnswers();
        String answer = ClarifyAnswerFormatter.format(answers, baseProductName(answers.getBaseProduct()));
        searchLogRepository.findByJobId(jobId).forEach(SearchLog::markClarified);

        AgentClarifyRequest aiRequest = new AgentClarifyRequest(jobId.toString(), answer);
        afterCommit(() -> {
            try {
                aiInternalClient.clarify(aiRequest);
            } catch (RuntimeException e) {
                log.warn("[RecommendationJob] AI 되묻기 답변 호출 실패: jobId={}, error={}", jobId, e.getMessage());
            }
        });
        return new ClarificationResponse(jobId, JobStatus.IN_PROGRESS);
    }

    /** 기준 제품 답이 상품 ID 면 AI 가 알아듣도록 제품 이름으로 바꾼다. 이름으로 왔거나 찾을 수 없으면 받은 그대로 */
    private String baseProductName(String baseProduct) {
        if (baseProduct == null || baseProduct.isBlank()) {
            return null;
        }
        try {
            return productRepository.findById(UUID.fromString(baseProduct.strip()))
                    .map(Product::getName)
                    .orElse(baseProduct);
        } catch (IllegalArgumentException e) {
            return baseProduct;
        }
    }

    /**
     * job 을 대기 상태로 만들고 검색 기록을 남긴 뒤, 커밋되면 AI 추천 실행을 부른다. 호출하는 쪽의 트랜잭션 안에서 불러야 한다.
     *
     * @param parentJobId 조건 수정이면 이어 온 부모 job
     */
    Recommendation startJob(User user, String rawQuery, RecommendationBasis basis, String targetProfile,
                            UUID parentJobId) {
        LocalDateTime now = LocalDateTime.now();
        Recommendation job = recommendationRepository.save(Recommendation.builder()
                .user(user)
                .status(JobStatus.PENDING)
                .progress(0)
                .rawQuery(rawQuery)
                .basis(basis)
                .targetProfile(targetProfile)
                .parentJobId(parentJobId)
                .createdAt(now)
                .updatedAt(now)
                .build());

        searchLogRepository.save(SearchLog.builder()
                .userId(user.getId())
                .jobId(job.getId())
                .rawQuery(rawQuery)
                .build());

        AgentRunV2Request aiRequest = new AgentRunV2Request(job.getId().toString(), user.getId().toString(),
                rawQuery, basis.name(), toMap(targetProfile), parentJobId == null ? null : parentJobId.toString());
        afterCommit(() -> runAgent(aiRequest));
        return job;
    }

    private void runAgent(AgentRunV2Request request) {
        try {
            aiInternalClient.runAgentV2(request);
        } catch (RuntimeException e) {
            // 비동기 호출이라 실패해도 접수 응답은 그대로 둔다
            log.warn("[RecommendationJob] AI 추천 실행 호출 실패: jobId={}, error={}", request.jobId(), e.getMessage());
        }
    }

    private Map<String, Object> toMap(String json) {
        return jsonUtil.read(json, new TypeReference<Map<String, Object>>() {
        });
    }

    /** 트랜잭션이 있으면 커밋된 뒤에, 없으면 바로 실행한다 */
    private static void afterCommit(Runnable action) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            action.run();
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                action.run();
            }
        });
    }
}
