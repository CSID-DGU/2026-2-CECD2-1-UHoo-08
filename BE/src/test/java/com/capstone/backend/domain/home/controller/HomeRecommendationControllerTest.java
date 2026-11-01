package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.CoveredCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.MissingCondition;
import com.capstone.backend.domain.home.enums.HomeRecommendationState;
import com.capstone.backend.domain.home.service.HomeRecommendationService;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.service.ResultAssembler;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.io.InputStream;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class HomeRecommendationControllerTest {

    @Mock
    HomeRecommendationService homeRecommendationService;
    @InjectMocks
    HomeRecommendationController controller;

    MockMvc mockMvc;

    private final UUID userId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                // 앱 설정(spring.jackson.serialization.write-dates-as-timestamps: false)과 같게 날짜를 문자열로 쓴다
                .setMessageConverters(new MappingJackson2HttpMessageConverter(Jackson2ObjectMapperBuilder.json()
                        .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build()))
                .setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
                .build();
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(userId, null, Collections.emptyList()));
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    /** 실제 결과 조립기로 홈 환경 결과 샘플을 조립한다 */
    private static RecommendationResultV2Response assembleSample(UUID jobId) throws Exception {
        try (InputStream in = HomeRecommendationControllerTest.class.getResourceAsStream("/ai-results/HOME_ENV.json")) {
            return new ResultAssembler(mock(ProductRepository.class)).assemble(new ResultAssembler.Source(
                    jobId, null, "HOME_ENV", RecommendationBasis.SELF, new ObjectMapper().readTree(in),
                    MissingNode.getInstance(), "OILY", MissingNode.getInstance()), null);
        }
    }

    @Test
    void 환경_기반_추천은_상태_조건_추천_결과_계산_시각을_내린다() throws Exception {
        UUID jobId = UUID.randomUUID();
        // 조립에 mock 을 쓰므로 스텁 밖에서 먼저 만든다
        RecommendationResultV2Response result = assembleSample(jobId);
        given(homeRecommendationService.getEnvironment(userId)).willReturn(new EnvironmentRecommendationResponse(
                HomeRecommendationState.READY,
                List.of(new MissingCondition("SOOTHING", "진정")),
                List.of(new CoveredCondition("UV_PROTECT", "자외선 차단", "닥터지 선크림")),
                result,
                OffsetDateTime.of(2026, 9, 20, 6, 10, 0, 0, ZoneOffset.UTC)));

        mockMvc.perform(get("/home/recommendations/environment"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.state").value("READY"))
                .andExpect(jsonPath("$.data.missingConditions[0].key").value("SOOTHING"))
                .andExpect(jsonPath("$.data.missingConditions[0].label").value("진정"))
                .andExpect(jsonPath("$.data.coveredConditions[0].coveredBy").value("닥터지 선크림"))
                .andExpect(jsonPath("$.data.result.jobId").value(jobId.toString()))
                .andExpect(jsonPath("$.data.result.scenario").value("HOME_ENV"))
                .andExpect(jsonPath("$.data.result.items[0].badges[0].type").value("ENV"))
                .andExpect(jsonPath("$.data.computedAt").value("2026-09-20T06:10:00Z"));
    }

    @Test
    void 아직_계산_전이면_NOT_READY와_null_결과를_내린다() throws Exception {
        given(homeRecommendationService.getEnvironment(userId)).willReturn(new EnvironmentRecommendationResponse(
                HomeRecommendationState.NOT_READY, List.of(), List.of(), null, null));

        mockMvc.perform(get("/home/recommendations/environment"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.state").value("NOT_READY"))
                .andExpect(jsonPath("$.data.missingConditions").isEmpty())
                .andExpect(content().string(containsString("\"result\":null")))
                .andExpect(content().string(containsString("\"computedAt\":null")));
    }

    @Test
    void 지역을_설정하지_않았으면_404_REGION_NOT_SET이다() throws Exception {
        given(homeRecommendationService.getEnvironment(userId)).willThrow(new BusinessException(ErrorCode.REGION_NOT_SET));

        mockMvc.perform(get("/home/recommendations/environment"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("REGION_NOT_SET"));
    }
}
