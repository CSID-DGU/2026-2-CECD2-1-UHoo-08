package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentClarifyRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentRunV2Request;
import com.capstone.backend.common.ai.dto.AiInternalDtos.FeedbackApplyRequest;
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

        Recommendation job = startJob(new NewJob(user, request.getQuery().strip(), basis, targetProfile, null, null, null));
        return new RecommendationQueryResponse(job.getId(), ESTIMATED_SECONDS,
                "/recommendations/" + job.getId() + "/status");
    }

    /**
     * 되묻는 중인 job 에 사용자의 답을 넘겨 같은 job 을 이어서 돌린다. 되묻는 중이 아니거나 이미 답을 받았으면 CLARIFY_NOT_REQUIRED.
     *
     * job 상태는 여기서 바꾸지 않는다. AI 는 job 이 아직 되묻는 중일 때만 답을 받아 이어 돌리고 그때 진행 중으로 바꾼다.
     * 먼저 진행 중으로 바꾸면 AI 가 답을 무시한다. 응답은 곧 진행될 상태(IN_PROGRESS)로 내린다.
     * 대신 검색 기록의 답 받음 표시를 조건부로 바꿔, 같은 job 에 답이 동시에 와도 한 요청만 AI 에 넘긴다.
     * AI 는 한 job 에 한 번만 되묻으므로 이 표시는 한 번만 바뀌면 된다.
     * AI 에 넘기지 못하면 표시를 되돌려, job 이 되묻는 중으로 남아 있는 동안 사용자가 답을 다시 보낼 수 있게 한다.
     */
    @Transactional
    public ClarificationResponse answerClarification(UUID userId, UUID jobId, ClarificationRequest request) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (job.getStatus() != JobStatus.NEEDS_CLARIFICATION) {
            throw new BusinessException(ErrorCode.CLARIFY_NOT_REQUIRED);
        }

        if (searchLogRepository.markClarified(jobId) == 0) {
            throw new BusinessException(ErrorCode.CLARIFY_NOT_REQUIRED);
        }

        Answers answers = request.getAnswers();
        String answer = ClarifyAnswerFormatter.format(answers, baseProductName(answers.getBaseProduct()));

        AgentClarifyRequest aiRequest = new AgentClarifyRequest(jobId.toString(), answer);
        afterCommit(() -> {
            try {
                aiInternalClient.clarify(aiRequest, () -> releaseClarification(jobId));
            } catch (RuntimeException e) {
                log.warn("[RecommendationJob] AI 되묻기 답변 호출 실패: jobId={}, error={}", jobId, e.getMessage());
                releaseClarification(jobId);
            }
        });
        return new ClarificationResponse(jobId, JobStatus.IN_PROGRESS);
    }

    /** 답을 AI 에 넘기지 못했으니 답 받음 표시를 되돌린다 */
    private void releaseClarification(UUID jobId) {
        try {
            searchLogRepository.unmarkClarified(jobId);
        } catch (RuntimeException e) {
            log.warn("[RecommendationJob] 되묻기 답변 표시 되돌리기 실패: jobId={}, error={}", jobId, e.getMessage());
        }
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
     * 새로 만들 job 의 값.
     *
     * @param parentJobId   조건 수정이면 이어 온 직전 job
     * @param refinePresets 조건 수정에서 고른 조건 키. 고르지 않았으면 null
     * @param refineText    조건 수정에서 직접 쓴 조건. 없으면 null
     */
    record NewJob(User user, String rawQuery, RecommendationBasis basis, String targetProfile,
                  UUID parentJobId, String[] refinePresets, String refineText) {
    }

    /**
     * job 을 대기 상태로 만들고 검색 기록을 남긴 뒤, 커밋되면 AI 추천 실행을 부른다. 호출하는 쪽의 트랜잭션 안에서 불러야 한다.
     * 조건 수정이면 직전 job 을 함께 알려, AI 가 직전 상태에서 조건을 이어받아 후보를 다시 찾게 한다.
     */
    Recommendation startJob(NewJob newJob) {
        User user = newJob.user();
        LocalDateTime now = LocalDateTime.now();
        Recommendation job = recommendationRepository.save(Recommendation.builder()
                .user(user)
                .status(JobStatus.PENDING)
                .progress(0)
                .rawQuery(newJob.rawQuery())
                .basis(newJob.basis())
                .targetProfile(newJob.targetProfile())
                .parentJobId(newJob.parentJobId())
                .refinePresets(newJob.refinePresets())
                .refineText(newJob.refineText())
                .createdAt(now)
                .updatedAt(now)
                .build());

        searchLogRepository.save(SearchLog.builder()
                .userId(user.getId())
                .jobId(job.getId())
                .rawQuery(newJob.rawQuery())
                .build());

        UUID parentJobId = newJob.parentJobId();
        AgentRunV2Request aiRequest = new AgentRunV2Request(job.getId().toString(), user.getId().toString(),
                newJob.rawQuery(), newJob.basis().name(), toMap(newJob.targetProfile()),
                parentJobId == null ? null : parentJobId.toString());
        afterCommit(() -> runAgent(aiRequest));
        return job;
    }

    /**
     * 커밋되면 AI 에 이 사용자의 가중치를 다시 계산하라고 알린다. 피드백과 조건 수정 패턴을 반영하는 규칙은 AI 에 있다.
     * 피드백 등록, 조건 수정, 가중치 변경 되돌리기 뒤에 부른다. 비동기 호출이고 실패해도 요청은 그대로 접수된다.
     */
    public void requestFeedbackApply(UUID userId) {
        FeedbackApplyRequest request = new FeedbackApplyRequest(userId.toString());
        afterCommit(() -> {
            try {
                aiInternalClient.applyFeedback(request);
            } catch (RuntimeException e) {
                log.warn("[RecommendationJob] AI 가중치 반영 호출 실패: userId={}, error={}", userId, e.getMessage());
            }
        });
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
