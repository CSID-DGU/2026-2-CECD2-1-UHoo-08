package com.capstone.backend.domain.recommendation.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Clarify;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusV2Response.Step;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.service.ClarifyFieldMapper;
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
}
