package com.capstone.backend.domain.recommendation.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.request.ClarificationRequest;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.response.ClarificationResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Clarify;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Step;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.service.ClarifyFieldMapper;
import com.capstone.backend.domain.recommendation.service.ResultAssembler;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.TargetPersonalColor;
import com.capstone.backend.domain.recommendation.enums.TargetRelation;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService;
import com.capstone.backend.domain.recommendation.service.RecommendationService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class RecommendationControllerTest {

    @Mock
    RecommendationService recommendationService;
    @Mock
    RecommendationJobService recommendationJobService;
    @InjectMocks
    RecommendationController controller;

    MockMvc mockMvc;

    private final UUID userId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
                .build();
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(userId, null, Collections.emptyList()));
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    // 자연어 추천 요청

    @Test
    void 추천을_요청하면_202와_jobId_예상_시간_상태_경로를_돌려준다() throws Exception {
        UUID jobId = UUID.randomUUID();
        ArgumentCaptor<RecommendationQueryRequest> request = ArgumentCaptor.forClass(RecommendationQueryRequest.class);
        given(recommendationJobService.requestQuery(eq(userId), request.capture())).willReturn(
                new RecommendationQueryResponse(jobId, 8, "/recommendations/" + jobId + "/status"));

        mockMvc.perform(post("/recommendations/queries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"query":"엄마 선물 쿠션","basis":"OTHER",
                                 "targetProfile":{"relation":"MOM","personalColor":"AUTUMN_MUTE"}}
                                """))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.jobId").value(jobId.toString()))
                .andExpect(jsonPath("$.data.estimatedSeconds").value(8))
                .andExpect(jsonPath("$.data.statusUrl").value("/recommendations/" + jobId + "/status"));

        assertThat(request.getValue().getBasis()).isEqualTo(RecommendationBasis.OTHER);
        assertThat(request.getValue().getTargetProfile().getRelation()).isEqualTo(TargetRelation.MOM);
        assertThat(request.getValue().getTargetProfile().getPersonalColor()).isEqualTo(TargetPersonalColor.AUTUMN_MUTE);
    }

    @Test
    void 문장이_비었으면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/recommendations/queries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"query":"  "}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 추천_기준이나_쓰실_분_정보의_값이_목록에_없으면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/recommendations/queries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"query":"쿠션","basis":"FRIENDS"}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        mockMvc.perform(post("/recommendations/queries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"query":"쿠션","basis":"OTHER","targetProfile":{"skinConcerns":["ACNE"]}}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 내_피부_기준인데_피부_정보가_없으면_404_SKIN_PROFILE_NOT_FOUND다() throws Exception {
        given(recommendationJobService.requestQuery(eq(userId), any()))
                .willThrow(new BusinessException(ErrorCode.SKIN_PROFILE_NOT_FOUND));

        mockMvc.perform(post("/recommendations/queries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"query":"쿠션"}
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("SKIN_PROFILE_NOT_FOUND"));
    }
    // 추천 진행 상태 조회

    @Test
    void 자연어_추천_job은_시나리오_진행_단계_되묻기를_더해_내린다() throws Exception {
        UUID jobId = UUID.randomUUID();
        Recommendation job = Recommendation.builder().id(jobId).status(JobStatus.NEEDS_CLARIFICATION)
                .scenario("S6_BUNDLE").step("되묻는 중").progress(10).basis(RecommendationBasis.SELF).build();
        given(recommendationService.getStatus(userId, jobId)).willReturn(new RecommendationStatusV2Response(job,
                List.of(new Step("normalize", "요청 이해", "DONE")),
                new Clarify("두 가지만 알려주시면 바로 찾아드릴게요", ClarifyFieldMapper.map("S6_BUNDLE", null))));

        mockMvc.perform(get("/recommendations/{jobId}/status", jobId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.jobId").value(jobId.toString()))
                .andExpect(jsonPath("$.data.status").value("NEEDS_CLARIFICATION"))
                .andExpect(jsonPath("$.data.scenario").value("S6_BUNDLE"))
                .andExpect(jsonPath("$.data.progress").value(10))
                .andExpect(jsonPath("$.data.step").value("되묻는 중"))
                .andExpect(jsonPath("$.data.steps[0].key").value("normalize"))
                .andExpect(jsonPath("$.data.steps[0].state").value("DONE"))
                .andExpect(jsonPath("$.data.clarify.message").value("두 가지만 알려주시면 바로 찾아드릴게요"))
                .andExpect(jsonPath("$.data.clarify.fields[0].key").value("budget"))
                .andExpect(jsonPath("$.data.clarify.fields[0].inputType").value("AMOUNT"))
                .andExpect(jsonPath("$.data.clarify.fields[0].presets[1]").value(50000))
                .andExpect(content().string(containsString("\"presets\":null")));
    }

    @Test
    void 판정_전이면_시나리오와_되묻기는_null로_내린다() throws Exception {
        UUID jobId = UUID.randomUUID();
        Recommendation job = Recommendation.builder().id(jobId).status(JobStatus.PENDING).progress(0)
                .basis(RecommendationBasis.SELF).build();
        given(recommendationService.getStatus(userId, jobId))
                .willReturn(new RecommendationStatusV2Response(job, List.of(), null));

        mockMvc.perform(get("/recommendations/{jobId}/status", jobId))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("\"scenario\":null")))
                .andExpect(content().string(containsString("\"clarify\":null")))
                .andExpect(jsonPath("$.data.steps").isEmpty());
    }

    @Test
    void 상품_기준_추천_job은_기존_필드만_내린다() throws Exception {
        UUID jobId = UUID.randomUUID();
        Recommendation job = Recommendation.builder().id(jobId).status(JobStatus.COMPLETED).step("완료").progress(100).build();
        given(recommendationService.getStatus(userId, jobId)).willReturn(RecommendationStatusResponse.from(job));

        mockMvc.perform(get("/recommendations/{jobId}/status", jobId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("COMPLETED"))
                .andExpect(jsonPath("$.data.progress").value(100))
                .andExpect(jsonPath("$.data.scenario").doesNotExist())
                .andExpect(jsonPath("$.data.steps").doesNotExist())
                .andExpect(jsonPath("$.data.clarify").doesNotExist());
    }

    @Test
    void 없거나_남의_job이면_404_NOT_FOUND다() throws Exception {
        UUID jobId = UUID.randomUUID();
        given(recommendationService.getStatus(userId, jobId)).willThrow(new BusinessException(ErrorCode.NOT_FOUND));

        mockMvc.perform(get("/recommendations/{jobId}/status", jobId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }
    // 추천 결과 조회

    @Test
    void 자연어_추천_결과는_공통_결과_형식으로_내린다() throws Exception {
        UUID jobId = UUID.randomUUID();
        RecommendationResultV2Response result = assembleSample(jobId, "S6_BUNDLE");
        given(recommendationService.getResult(userId, jobId)).willReturn(result);

        mockMvc.perform(get("/recommendations/{jobId}", jobId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.jobId").value(jobId.toString()))
                .andExpect(jsonPath("$.data.scenario").value("S6_BUNDLE"))
                .andExpect(jsonPath("$.data.basis").value("SELF"))
                .andExpect(jsonPath("$.data.summary.categoryLabel").value("스킨케어"))
                .andExpect(jsonPath("$.data.summary.conditions[3]").value("총 10만원"))
                .andExpect(jsonPath("$.data.excluded.count").value(0))
                .andExpect(jsonPath("$.data.alternativesDroppedCount").value(0))
                .andExpect(jsonPath("$.data.bundles[0].index").value(1))
                .andExpect(jsonPath("$.data.bundles[0].remaining").value(8000))
                .andExpect(jsonPath("$.data.bundles[0].slots[2].slotKey").value("2"))
                .andExpect(content().string(containsString("\"parentJobId\":null")))
                .andExpect(content().string(containsString("\"appliedPreference\":null")))
                .andExpect(content().string(containsString("\"type\":null")))
                .andExpect(jsonPath("$.data.similarUserProducts").isEmpty());
    }

    @Test
    void 완료되지_않은_job의_결과를_읽으면_409_JOB_NOT_COMPLETED다() throws Exception {
        UUID jobId = UUID.randomUUID();
        given(recommendationService.getResult(userId, jobId)).willThrow(new BusinessException(ErrorCode.JOB_NOT_COMPLETED));

        mockMvc.perform(get("/recommendations/{jobId}", jobId))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("JOB_NOT_COMPLETED"));
    }

    // 추가 질문 답변

    @Test
    void 답을_보내면_202와_같은_jobId와_진행_중_상태를_돌려준다() throws Exception {
        UUID jobId = UUID.randomUUID();
        ArgumentCaptor<ClarificationRequest> request = ArgumentCaptor.forClass(ClarificationRequest.class);
        given(recommendationJobService.answerClarification(eq(userId), eq(jobId), request.capture()))
                .willReturn(new ClarificationResponse(jobId, JobStatus.IN_PROGRESS));

        mockMvc.perform(post("/recommendations/{jobId}/clarifications", jobId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"answers":{"budget":50000,"bundleSteps":["스킨","로션","선크림"]}}
                                """))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.data.jobId").value(jobId.toString()))
                .andExpect(jsonPath("$.data.status").value("IN_PROGRESS"));

        assertThat(request.getValue().getAnswers().getBudget()).isEqualTo(50000);
        assertThat(request.getValue().getAnswers().getBundleSteps()).containsExactly("스킨", "로션", "선크림");
    }

    @Test
    void 답이_하나도_없으면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/recommendations/{jobId}/clarifications", UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"answers":{"text":"  "}}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        mockMvc.perform(post("/recommendations/{jobId}/clarifications", UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isUnprocessableEntity());
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 되묻는_중이_아닌_job에_답하면_409_CLARIFY_NOT_REQUIRED다() throws Exception {
        UUID jobId = UUID.randomUUID();
        given(recommendationJobService.answerClarification(eq(userId), eq(jobId), any()))
                .willThrow(new BusinessException(ErrorCode.CLARIFY_NOT_REQUIRED));

        mockMvc.perform(post("/recommendations/{jobId}/clarifications", jobId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"answers":{"text":"쿠션"}}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("CLARIFY_NOT_REQUIRED"));
    }

    /** 실제 조립 결과로 응답 모양을 확인한다. 상품 정보는 비워 둔다 */
    private static RecommendationResultV2Response assembleSample(UUID jobId, String scenario) throws Exception {
        try (var in = RecommendationControllerTest.class.getResourceAsStream("/ai-results/" + scenario + ".json")) {
            ResultAssembler assembler = new ResultAssembler(mock(ProductRepository.class));
            return assembler.assemble(new ResultAssembler.Source(jobId, null, scenario, RecommendationBasis.SELF,
                    new ObjectMapper().readTree(in), MissingNode.getInstance(), null, MissingNode.getInstance()), null);
        }
    }
}
