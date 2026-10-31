package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.SeasonChange;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Stats;
import com.capstone.backend.domain.home.service.EnvironmentService;
import com.fasterxml.jackson.databind.SerializationFeature;
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

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class EnvironmentControllerTest {

    @Mock
    EnvironmentService environmentService;
    @InjectMocks
    EnvironmentController controller;

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

    @Test
    void 환경_요약은_기간_통계_계절_전환_조건을_내린다() throws Exception {
        given(environmentService.getSummary(userId)).willReturn(new EnvironmentSummaryResponse(
                "고양시 덕양구", LocalDate.of(2026, 8, 20), LocalDate.of(2026, 9, 16), 28,
                new Stats(22, 14, 41),
                new SeasonChange("계절이 바뀌고 있어요", "습도가 3주 만에 62% → 41%로 떨어졌어요"),
                List.of(new Condition("SOOTHING", "진정, 항산화", "미세먼지 14일", false, null)),
                1, null));

        mockMvc.perform(get("/environment/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.regionName").value("고양시 덕양구"))
                .andExpect(jsonPath("$.data.periodStart").value("2026-08-20"))
                .andExpect(jsonPath("$.data.periodEnd").value("2026-09-16"))
                .andExpect(jsonPath("$.data.dayCount").value(28))
                .andExpect(jsonPath("$.data.stats.uvHighDays").value(22))
                .andExpect(jsonPath("$.data.stats.dustBadDays").value(14))
                .andExpect(jsonPath("$.data.stats.avgHumidity").value(41))
                .andExpect(jsonPath("$.data.seasonChange.message").value("습도가 3주 만에 62% → 41%로 떨어졌어요"))
                .andExpect(jsonPath("$.data.conditions[0].key").value("SOOTHING"))
                .andExpect(jsonPath("$.data.conditions[0].covered").value(false))
                .andExpect(content().string(containsString("\"coveredBy\":null")))
                .andExpect(jsonPath("$.data.missingCount").value(1))
                .andExpect(content().string(containsString("\"updatedAt\":null")));
    }

    @Test
    void 지역을_설정하지_않았으면_404_REGION_NOT_SET이다() throws Exception {
        given(environmentService.getSummary(userId)).willThrow(new BusinessException(ErrorCode.REGION_NOT_SET));

        mockMvc.perform(get("/environment/summary"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("REGION_NOT_SET"));
    }
}
