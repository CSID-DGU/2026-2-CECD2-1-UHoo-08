package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.request.RefinementRequest;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse.Preset;
import com.capstone.backend.domain.recommendation.dto.response.RefinementResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService.NewJob;
import com.capstone.backend.domain.user.entity.User;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class RecommendationRefineServiceTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 29, 12, 0);

    @Mock
    RecommendationRepository recommendationRepository;
    @Mock
    RecommendationJobService recommendationJobService;

    RecommendationRefineService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new RecommendationRefineService(recommendationRepository, new JsonUtil(new ObjectMapper()),
                recommendationJobService);
    }

    private void givenJob(Recommendation job) {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(job));
    }

    private Recommendation.RecommendationBuilder completedJob() {
        return Recommendation.builder().id(jobId).status(JobStatus.COMPLETED).progress(100).basis(RecommendationBasis.SELF);
    }

    @Test
    void 지금_조건은_결과_상단_조건_칩과_같고_선택지는_여섯_개다() {
        givenJob(completedJob()
                .result("{\"query\":{\"conditions\":[\"쿠션\",\"매트\"],\"budgetMax\":30000}}").build());
        given(recommendationRepository.findRefinePresetsSince(userId, NOW.minusDays(30))).willReturn(List.of());

        RefinementOptionsResponse response = service.getOptions(userId, jobId, NOW);

        assertThat(response.getCurrentConditions()).containsExactly("쿠션", "매트", "3만원 이하");
        assertThat(response.getPresets()).extracting(Preset::getKey).containsExactly(RefinePreset.values());
        assertThat(response.getPresets().get(0).getLabel()).isEqualTo("더 저렴하게");
        assertThat(response.getPresets()).noneMatch(Preset::isFrequent);
    }

    @Test
    void 최근_30일_동안_두_번_이상_고른_조건을_자주_고른_조건으로_표시한다() {
        givenJob(completedJob().result("{}").build());
        given(recommendationRepository.findRefinePresetsSince(userId, NOW.minusDays(30))).willReturn(List.of(
                new String[]{"CHEAPER", "UNSCENTED"},
                new String[]{"CHEAPER"},
                new String[]{"UNSCENTED"},
                new String[]{"UV_PROTECT"}));

        RefinementOptionsResponse response = service.getOptions(userId, jobId, NOW);

        assertThat(response.getPresets()).filteredOn(Preset::isFrequent).extracting(Preset::getKey)
                .containsExactly(RefinePreset.CHEAPER, RefinePreset.UNSCENTED);
    }

    @Test
    void 결과가_아직_없거나_상품_기준_추천_job이면_지금_조건은_비어_있다() {
        given(recommendationRepository.findRefinePresetsSince(any(), any())).willReturn(List.of());
        givenJob(Recommendation.builder().id(jobId).status(JobStatus.IN_PROGRESS).progress(30)
                .basis(RecommendationBasis.SELF).build());
        assertThat(service.getOptions(userId, jobId, NOW).getCurrentConditions()).isEmpty();

        givenJob(Recommendation.builder().id(jobId).status(JobStatus.COMPLETED).progress(100)
                .result("{\"matchScore\":80}").build());
        assertThat(service.getOptions(userId, jobId, NOW).getCurrentConditions()).isEmpty();
    }

    @Test
    void 결과를_읽을_수_없어도_실패하지_않고_지금_조건을_비운다() {
        givenJob(completedJob().result("{broken").build());
        given(recommendationRepository.findRefinePresetsSince(any(), any())).willReturn(List.of());

        assertThat(service.getOptions(userId, jobId, NOW).getCurrentConditions()).isEmpty();
    }

    @Test
    void 남의_job이면_NOT_FOUND다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getOptions(userId, jobId, NOW))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
    }
    // 조건 추가(재탐색)

    private final UUID newJobId = UUID.randomUUID();

    private User user() {
        return User.builder().id(userId).name("하림").provider("KAKAO").skinType("OILY").build();
    }

    private ArgumentCaptor<NewJob> givenStartJob() {
        ArgumentCaptor<NewJob> captor = ArgumentCaptor.forClass(NewJob.class);
        given(recommendationJobService.startJob(captor.capture()))
                .willReturn(Recommendation.builder().id(newJobId).status(JobStatus.PENDING).progress(0).build());
        return captor;
    }

    @Test
    void 직전_job의_추천_기준과_쓰실_분_정보를_이어받아_새_job을_만들고_가중치_반영을_알린다() {
        User user = user();
        givenJob(completedJob().user(user).basis(RecommendationBasis.OTHER).targetProfile("{\"relation\":\"MOM\"}").build());
        ArgumentCaptor<NewJob> newJob = givenStartJob();

        RefinementResponse response = service.refine(userId, jobId, RefinementRequest.builder()
                .presetKeys(List.of(RefinePreset.UNSCENTED, RefinePreset.CHEAPER)).freeText(" 팩트 말고 쿠션만 보여줘 ").build());

        assertThat(response.getJobId()).isEqualTo(newJobId);
        assertThat(response.getParentJobId()).isEqualTo(jobId);
        assertThat(response.getEstimatedSeconds()).isEqualTo(4);

        NewJob value = newJob.getValue();
        assertThat(value.user()).isSameAs(user);
        assertThat(value.parentJobId()).isEqualTo(jobId);
        assertThat(value.basis()).isEqualTo(RecommendationBasis.OTHER);
        assertThat(value.targetProfile()).isEqualTo("{\"relation\":\"MOM\"}");
        // 고른 조건은 선택지 순서로, 직접 쓴 조건은 뒤에 붙인다
        assertThat(value.refinePresets()).containsExactly("CHEAPER", "UNSCENTED");
        assertThat(value.refineText()).isEqualTo("팩트 말고 쿠션만 보여줘");
        assertThat(value.rawQuery()).isEqualTo("더 저렴한 제품으로, 무향 제품으로, 팩트 말고 쿠션만 보여줘");
        verify(recommendationJobService).requestFeedbackApply(userId);
    }

    @Test
    void 직접_쓴_조건만_있으면_고른_조건은_비워_둔다() {
        givenJob(completedJob().user(user()).build());
        ArgumentCaptor<NewJob> newJob = givenStartJob();

        service.refine(userId, jobId, RefinementRequest.builder().freeText("쿠션만").build());

        assertThat(newJob.getValue().refinePresets()).isNull();
        assertThat(newJob.getValue().rawQuery()).isEqualTo("쿠션만");
    }

    @Test
    void 같은_조건이_겹쳐_와도_한_번만_남긴다() {
        assertThat(RecommendationRefineService.presetsOf(RefinementRequest.builder()
                .presetKeys(Arrays.asList(RefinePreset.UV_PROTECT, null, RefinePreset.UV_PROTECT)).build()))
                .containsExactly(RefinePreset.UV_PROTECT);
    }

    @Test
    void 고른_조건도_직접_쓴_조건도_없으면_VALIDATION_ERROR다() {
        givenJob(completedJob().user(user()).build());

        assertThatThrownBy(() -> service.refine(userId, jobId,
                RefinementRequest.builder().presetKeys(List.of()).freeText("  ").build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 직전_job이_끝나지_않았으면_JOB_NOT_COMPLETED다() {
        givenJob(Recommendation.builder().id(jobId).status(JobStatus.IN_PROGRESS).progress(50)
                .basis(RecommendationBasis.SELF).build());

        assertThatThrownBy(() -> service.refine(userId, jobId,
                RefinementRequest.builder().presetKeys(List.of(RefinePreset.CHEAPER)).build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.JOB_NOT_COMPLETED);
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 상품_기준_추천_job은_이어_갈_수_없어_VALIDATION_ERROR다() {
        givenJob(Recommendation.builder().id(jobId).status(JobStatus.COMPLETED).progress(100).build());

        assertThatThrownBy(() -> service.refine(userId, jobId,
                RefinementRequest.builder().presetKeys(List.of(RefinePreset.CHEAPER)).build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 남의_job에_조건을_더하면_NOT_FOUND다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.refine(userId, jobId,
                RefinementRequest.builder().presetKeys(List.of(RefinePreset.CHEAPER)).build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
    }
}
