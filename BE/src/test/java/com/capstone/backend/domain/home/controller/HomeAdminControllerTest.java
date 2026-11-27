package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.service.HomeAdminService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
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

import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class HomeAdminControllerTest {

    @Mock
    HomeAdminService homeAdminService;
    @InjectMocks
    HomeAdminController controller;

    MockMvc mockMvc;

    private final UUID adminId = UUID.randomUUID();
    private final UUID userId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
                .build();
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(adminId, null, Collections.emptyList()));
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    private String body(String kind) {
        return "{\"userId\":\"" + userId + "\",\"kind\":\"" + kind + "\"}";
    }

    @Test
    void 요청하면_202이고_호출한_사람과_대상을_넘긴다() throws Exception {
        mockMvc.perform(post("/admin/home/run").contentType(MediaType.APPLICATION_JSON).content(body("ROUTINE")))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.success").value(true));

        verify(homeAdminService).requestCard(adminId, userId, HomeRecommendationKind.ROUTINE);
    }

    @Test
    void 관리자가_아니면_403_FORBIDDEN이다() throws Exception {
        willThrow(new BusinessException(ErrorCode.FORBIDDEN))
                .given(homeAdminService).requestCard(adminId, userId, HomeRecommendationKind.ENV);

        mockMvc.perform(post("/admin/home/run").contentType(MediaType.APPLICATION_JSON).content(body("ENV")))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error.code").value("FORBIDDEN"));
    }

    @Test
    void 없는_카드_종류나_빠진_값이면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/admin/home/run").contentType(MediaType.APPLICATION_JSON).content(body("WEEKLY")))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        mockMvc.perform(post("/admin/home/run").contentType(MediaType.APPLICATION_JSON).content("{\"kind\":\"ENV\"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(homeAdminService);
    }
}
