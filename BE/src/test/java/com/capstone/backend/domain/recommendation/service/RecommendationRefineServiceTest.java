package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse.Preset;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class RecommendationRefineServiceTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 29, 12, 0);

    @Mock
    RecommendationRepository recommendationRepository;

    RecommendationRefineService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new RecommendationRefineService(recommendationRepository, new JsonUtil(new ObjectMapper()));
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
}
