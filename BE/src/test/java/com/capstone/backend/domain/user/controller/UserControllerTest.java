package com.capstone.backend.domain.user.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.user.dto.request.RegionUpdateRequest;
import com.capstone.backend.domain.user.dto.response.RegionResponse;
import com.capstone.backend.domain.user.service.UserProfileService;
import com.capstone.backend.domain.user.service.UserService;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class UserControllerTest {

    @Mock
    UserService userService;
    @Mock
    UserProfileService userProfileService;
    @InjectMocks
    UserController controller;

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

    @Test
    void 지역을_저장하면_200과_저장한_지역을_돌려준다() throws Exception {
        ArgumentCaptor<RegionUpdateRequest> request = ArgumentCaptor.forClass(RegionUpdateRequest.class);
        given(userService.updateRegion(eq(userId), request.capture()))
                .willReturn(new RegionResponse("경기", "고양시 덕양구"));

        mockMvc.perform(patch("/users/me/region")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"regionCode":"경기","regionName":"고양시 덕양구"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.regionCode").value("경기"))
                .andExpect(jsonPath("$.data.regionName").value("고양시 덕양구"));

        assertThat(request.getValue().getRegionCode()).isEqualTo("경기");
        assertThat(request.getValue().getRegionName()).isEqualTo("고양시 덕양구");
    }

    @Test
    void 값이_비었거나_표시_이름이_50자를_넘으면_422_VALIDATION_ERROR다() throws Exception {
        for (String body : List.of(
                "{\"regionName\":\"고양시 덕양구\"}",
                "{\"regionCode\":\"경기\",\"regionName\":\" \"}",
                "{\"regionCode\":\"경기\",\"regionName\":\"" + "가".repeat(51) + "\"}")) {
            mockMvc.perform(patch("/users/me/region")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(body))
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        }
        verifyNoInteractions(userService);
    }

    @Test
    void 지원하지_않는_지역이면_422_VALIDATION_ERROR다() throws Exception {
        given(userService.updateRegion(eq(userId), any())).willThrow(new BusinessException(ErrorCode.VALIDATION_ERROR));

        mockMvc.perform(patch("/users/me/region")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"regionCode":"41281","regionName":"고양시 덕양구"}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
    }
}
