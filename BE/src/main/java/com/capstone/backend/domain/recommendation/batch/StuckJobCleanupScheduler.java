package com.capstone.backend.domain.recommendation.batch;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;

/**
 * 멈춘 추천 job 정리.
 *
 * AI 호출이 실패하거나 AI 가 job 을 끝내지 못하면 job 이 대기, 진행 중으로 남고, 화면은 끝없이 폴링한다.
 * 오래 갱신되지 않은 job 을 실패로 바꿔 화면이 실패를 보여 주고 재시도하게 한다.
 * 되묻는 중인 job 은 사용자의 답을 기다리는 정상 상태라 따로 길게 기다린다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StuckJobCleanupScheduler {

    static final String TIMEOUT = "timeout";
    static final String CLARIFICATION_TIMEOUT = "clarification timeout";

    private final RecommendationRepository recommendationRepository;
    private final HwadamProperties hwadamProperties;

    @Scheduled(cron = "${hwadam.batch.stuck-job-cleanup-cron}", zone = "${hwadam.batch.zone}")
    @Transactional
    public void failStuckJobs() {
        failStuckJobs(LocalDateTime.now(ZoneOffset.UTC));
    }

    void failStuckJobs(LocalDateTime now) {
        HwadamProperties.Batch batch = hwadamProperties.getBatch();

        int stuck = recommendationRepository.failStale(List.of(JobStatus.PENDING, JobStatus.IN_PROGRESS),
                now.minus(batch.getStuckJobTimeout()), TIMEOUT, now);
        int unanswered = recommendationRepository.failStale(List.of(JobStatus.NEEDS_CLARIFICATION),
                now.minus(batch.getClarificationTimeout()), CLARIFICATION_TIMEOUT, now);

        if (stuck + unanswered > 0) {
            log.info("[StuckJobCleanup] 멈춘 job {}건, 답을 받지 못한 되묻기 job {}건을 실패로 바꿈", stuck, unanswered);
        }
    }
}
