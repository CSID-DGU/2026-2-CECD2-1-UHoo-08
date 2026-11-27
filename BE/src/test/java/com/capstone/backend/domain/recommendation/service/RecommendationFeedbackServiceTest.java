package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.request.FeedbackRequest;
import com.capstone.backend.domain.recommendation.dto.response.FeedbackResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.FeedbackReason;
import com.capstone.backend.domain.recommendation.enums.FeedbackVote;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.repository.RecommendationFeedbackRepository;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class RecommendationFeedbackServiceTest {

    @Mock
    RecommendationRepository recommendationRepository;
    @Mock
    RecommendationFeedbackRepository feedbackRepository;
    @Mock
    RecommendationJobService recommendationJobService;

    RecommendationFeedbackService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();
    private final UUID alternativeId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new RecommendationFeedbackService(recommendationRepository, feedbackRepository,
                recommendationJobService, new JsonUtil(new ObjectMapper()));
    }

    private void givenCompletedJob() {
        String result = "{\"items\":[{\"productId\":\"" + productId + "\"},{\"productId\":null}],"
                + "\"alternatives\":[{\"productId\":\"" + alternativeId + "\"}]}";
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(
                Recommendation.builder().id(jobId).status(JobStatus.COMPLETED).progress(100)
                        .basis(RecommendationBasis.SELF).result(result).build()));
    }

    private static FeedbackRequest request(UUID productId, FeedbackVote vote, List<FeedbackReason> reasons) {
        return FeedbackRequest.builder().productId(productId).vote(vote).reasonTags(reasons).build();
    }

    @Test
    void 별로예요는_이유와_함께_저장하고_AI에_가중치_반영을_알린다() {
        givenCompletedJob();
        given(feedbackRepository.upsert(jobId, userId, productId, "DOWN", "{TOO_EXPENSIVE,BAD_REVIEWS}"))
                .willReturn(301L);

        FeedbackResponse response = service.submit(userId, jobId, request(productId, FeedbackVote.DOWN,
                List.of(FeedbackReason.BAD_REVIEWS, FeedbackReason.TOO_EXPENSIVE, FeedbackReason.BAD_REVIEWS)));

        assertThat(response.getFeedbackId()).isEqualTo("301");
        assertThat(response.getMessage()).isEqualTo("의견을 다음 추천에 반영할게요");
        assertThat(response.getChangeId()).isNull();
        verify(recommendationJobService).requestFeedbackApply(userId);
    }

    @Test
    void 좋아요는_이유를_버리고_좋아요_문구를_돌려준다() {
        givenCompletedJob();
        given(feedbackRepository.upsert(jobId, userId, productId, "UP", "{}")).willReturn(302L);

        FeedbackResponse response = service.submit(userId, jobId,
                request(productId, FeedbackVote.UP, List.of(FeedbackReason.TOO_EXPENSIVE)));

        assertThat(response.getMessage()).isEqualTo("좋아하신 점을 다음 추천에도 반영할게요");
    }

    @Test
    void 이유가_없는_별로예요는_빈_배열로_저장한다() {
        assertThat(RecommendationFeedbackService.reasonTagsOf(FeedbackVote.DOWN, null)).isEqualTo("{}");
        assertThat(RecommendationFeedbackService.reasonTagsOf(FeedbackVote.DOWN, List.of())).isEqualTo("{}");
    }

    @Test
    void 추천_목록에_없는_제품이면_VALIDATION_ERROR다() {
        givenCompletedJob();

        assertThatThrownBy(() -> service.submit(userId, jobId, request(alternativeId, FeedbackVote.UP, null)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        verifyNoInteractions(feedbackRepository, recommendationJobService);
    }

    @Test
    void 결과가_아직_없으면_VALIDATION_ERROR다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(
                Recommendation.builder().id(jobId).status(JobStatus.IN_PROGRESS).progress(30)
                        .basis(RecommendationBasis.SELF).build()));

        assertThatThrownBy(() -> service.submit(userId, jobId, request(productId, FeedbackVote.UP, null)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        verifyNoInteractions(feedbackRepository);
    }

    @Test
    void 남의_job에_피드백하면_NOT_FOUND다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.submit(userId, jobId, request(productId, FeedbackVote.UP, null)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
        verifyNoInteractions(feedbackRepository);
    }
}
