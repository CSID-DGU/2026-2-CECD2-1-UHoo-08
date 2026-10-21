package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.response.ClarifyFieldResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Step;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.entity.SearchLog;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.repository.SearchLogRepository;
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
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationServiceImplTest {

    @Mock
    RecommendationRepository recommendationRepository;
    @Mock
    SearchLogRepository searchLogRepository;

    RecommendationServiceImpl service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        service = new RecommendationServiceImpl(recommendationRepository, null, null, null, objectMapper,
                searchLogRepository, new JsonUtil(objectMapper));
    }

    private Recommendation.RecommendationBuilder v2Job(JobStatus status) {
        return Recommendation.builder().id(jobId).status(status).progress(40).basis(RecommendationBasis.SELF);
    }

    private void givenJob(Recommendation job) {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.of(job));
    }

    private RecommendationStatusV2Response statusV2() {
        RecommendationStatusResponse response = service.getStatus(userId, jobId);
        assertThat(response).isInstanceOf(RecommendationStatusV2Response.class);
        return (RecommendationStatusV2Response) response;
    }

    // 상품 기준 추천(v1) job

    @Test
    void 상품_기준_추천_job은_기존_응답_모양_그대로_내린다() {
        givenJob(Recommendation.builder().id(jobId).status(JobStatus.IN_PROGRESS).step("검색 중").progress(40).build());

        RecommendationStatusResponse response = service.getStatus(userId, jobId);

        assertThat(response).isExactlyInstanceOf(RecommendationStatusResponse.class);
        assertThat(response.getStatus()).isEqualTo("IN_PROGRESS");
        assertThat(response.getStep()).isEqualTo("검색 중");
        verify(searchLogRepository, never()).findByJobId(any());
    }

    @Test
    void 완료되지_않은_job의_결과를_읽으면_JOB_NOT_COMPLETED다() {
        givenJob(Recommendation.builder().id(jobId).status(JobStatus.NEEDS_CLARIFICATION).progress(0).build());

        assertThatThrownBy(() -> service.getResult(userId, jobId))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.JOB_NOT_COMPLETED);
    }

    // 자연어 추천 job

    @Test
    void 진행_중이면_시나리오와_기록된_진행_단계를_내리고_되묻기는_없다() {
        givenJob(v2Job(JobStatus.IN_PROGRESS).scenario("S2_SEARCH").step("적합도 계산")
                .steps("[{\"key\":\"normalize\",\"label\":\"요청 이해\",\"state\":\"DONE\"},"
                        + "{\"key\":\"score\",\"label\":\"적합도 계산\",\"state\":\"NOW\"}]").build());

        RecommendationStatusV2Response response = statusV2();

        assertThat(response.getScenario()).isEqualTo("S2_SEARCH");
        assertThat(response.getProgress()).isEqualTo(40);
        assertThat(response.getSteps()).extracting(Step::getKey, Step::getState)
                .containsExactly(tuple("normalize", "DONE"),
                        tuple("score", "NOW"));
        assertThat(response.getClarify()).isNull();
        // 진행 중에는 검색 기록을 건드리지 않는다
        verify(searchLogRepository, never()).findByJobId(any());
    }

    @Test
    void 진행_단계_목록이_없으면_현재_단계_문구_하나로_대신한다() {
        givenJob(v2Job(JobStatus.IN_PROGRESS).step("요청 이해").build());

        assertThat(statusV2().getSteps()).extracting(Step::getKey, Step::getLabel, Step::getState)
                .containsExactly(tuple("current", "요청 이해", "NOW"));
    }

    @Test
    void 진행_단계_목록이_깨졌어도_조회는_실패하지_않고_현재_단계로_대신한다() {
        givenJob(v2Job(JobStatus.IN_PROGRESS).step("요청 이해").steps("[{broken").build());

        assertThat(statusV2().getSteps()).extracting(Step::getKey).containsExactly("current");
    }

    @Test
    void 대기_중이라_단계_문구도_없으면_빈_목록이다() {
        givenJob(v2Job(JobStatus.PENDING).build());

        RecommendationStatusV2Response response = statusV2();

        assertThat(response.getSteps()).isEmpty();
        assertThat(response.getScenario()).isNull();
    }

    @Test
    void 되묻는_중이면_AI의_질문과_시나리오에_맞는_항목을_내린다() {
        givenJob(v2Job(JobStatus.NEEDS_CLARIFICATION).scenario("S6_BUNDLE").step("되묻는 중")
                .result("{\"clarify\":{\"question\":\"두 가지만 알려주시면 바로 찾아드릴게요\",\"options\":[]}}").build());
        given(searchLogRepository.findByJobId(jobId)).willReturn(List.of());

        RecommendationStatusV2Response response = statusV2();

        assertThat(response.getClarify().getMessage()).isEqualTo("두 가지만 알려주시면 바로 찾아드릴게요");
        assertThat(response.getClarify().getFields()).extracting(ClarifyFieldResponse::getKey)
                .containsExactly("budget", "bundleSteps");
    }

    @Test
    void 되묻는_중인데_질문이_없으면_기본_문구를_쓴다() {
        givenJob(v2Job(JobStatus.NEEDS_CLARIFICATION).scenario("S2_SEARCH").build());
        given(searchLogRepository.findByJobId(jobId)).willReturn(List.of());

        RecommendationStatusV2Response response = statusV2();

        assertThat(response.getClarify().getMessage()).isEqualTo("조금만 더 알려주시면 바로 찾아드릴게요");
        assertThat(response.getClarify().getFields()).extracting(ClarifyFieldResponse::getKey).containsExactly("category");
    }

    @Test
    void 처음_끝난_상태가_되면_검색_기록에_시나리오와_해석_결과와_확신도를_남긴다() {
        String spec = "{\"category\":\"base\",\"confidence\":0.82}";
        givenJob(v2Job(JobStatus.COMPLETED).scenario("S2_SEARCH").querySpec(spec).build());
        SearchLog searchLog = SearchLog.builder().jobId(jobId).rawQuery("쿠션").build();
        given(searchLogRepository.findByJobId(jobId)).willReturn(List.of(searchLog));

        service.getStatus(userId, jobId);

        assertThat(searchLog.getScenario()).isEqualTo("S2_SEARCH");
        assertThat(searchLog.getQuerySpec()).isEqualTo(spec);
        assertThat(searchLog.getConfidence()).isEqualTo(0.82f);
    }

    @Test
    void 이미_해석_결과를_남긴_검색_기록은_다시_채우지_않는다() {
        givenJob(v2Job(JobStatus.COMPLETED).scenario("S6_BUNDLE").querySpec("{\"confidence\":0.9}").build());
        SearchLog searchLog = SearchLog.builder().jobId(jobId).rawQuery("세트").scenario("S2_SEARCH")
                .querySpec("{\"confidence\":0.4}").confidence(0.4f).build();
        given(searchLogRepository.findByJobId(jobId)).willReturn(List.of(searchLog));

        service.getStatus(userId, jobId);

        assertThat(searchLog.getScenario()).isEqualTo("S2_SEARCH");
        assertThat(searchLog.getConfidence()).isEqualTo(0.4f);
    }

    @Test
    void 해석_전에_실패한_job은_확신도_없이_남긴다() {
        givenJob(v2Job(JobStatus.FAILED).build());
        SearchLog searchLog = SearchLog.builder().jobId(jobId).rawQuery("쿠션").build();
        given(searchLogRepository.findByJobId(jobId)).willReturn(List.of(searchLog));

        service.getStatus(userId, jobId);

        assertThat(searchLog.getScenario()).isNull();
        assertThat(searchLog.getConfidence()).isNull();
    }

    @Test
    void 남의_job이면_NOT_FOUND다() {
        given(recommendationRepository.findByIdAndUserId(jobId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getStatus(userId, jobId))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
    }

    @Test
    void 더_진행되지_않는_상태는_완료와_실패뿐이다() {
        assertThat(JobStatus.COMPLETED.isFinal()).isTrue();
        assertThat(JobStatus.FAILED.isFinal()).isTrue();
        assertThat(JobStatus.NEEDS_CLARIFICATION.isFinal()).isFalse();
        assertThat(JobStatus.PENDING.isFinal()).isFalse();
    }
}
