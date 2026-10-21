package com.capstone.backend.domain.recommendation.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
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
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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
}
