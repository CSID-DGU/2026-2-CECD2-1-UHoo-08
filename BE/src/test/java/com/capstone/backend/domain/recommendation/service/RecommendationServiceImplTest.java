package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class RecommendationServiceImplTest {

    @Mock
    RecommendationRepository recommendationRepository;
    @InjectMocks
    RecommendationServiceImpl service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    private void givenJob(JobStatus status) {
        Recommendation job = Recommendation.builder().id(jobId).status(status).step("검색 중").progress(40).build();
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(job));
    }

    @Test
    void 상태_조회는_job_상태를_이름_그대로_내린다() {
        givenJob(JobStatus.IN_PROGRESS);

        assertThat(service.getStatus(userId, jobId).getStatus()).isEqualTo("IN_PROGRESS");
    }

    @Test
    void 완료되지_않은_job의_결과를_읽으면_JOB_NOT_COMPLETED다() {
        givenJob(JobStatus.NEEDS_CLARIFICATION);

        assertThatThrownBy(() -> service.getResult(userId, jobId))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.JOB_NOT_COMPLETED);
    }

    @Test
    void 더_진행되지_않는_상태는_완료와_실패뿐이다() {
        assertThat(JobStatus.COMPLETED.isFinal()).isTrue();
        assertThat(JobStatus.FAILED.isFinal()).isTrue();
        assertThat(JobStatus.NEEDS_CLARIFICATION.isFinal()).isFalse();
        assertThat(JobStatus.PENDING.isFinal()).isFalse();
    }
}
