package com.capstone.backend.domain.auth.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.auth.dto.GoogleLoginRequest;
import com.capstone.backend.domain.auth.dto.TokenResponse;
import com.capstone.backend.domain.auth.service.AuthService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class AuthControllerTest {

    @Mock
    AuthService authService;
    @InjectMocks
    AuthController controller;

    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void 구글_인가_코드로_로그인하면_토큰을_돌려준다() throws Exception {
        UUID userId = UUID.randomUUID();
        given(authService.googleLogin(any())).willReturn(TokenResponse.builder()
                .accessToken("access")
                .refreshToken("refresh")
                .isNewUser(true)
                .user(TokenResponse.UserInfo.builder().id(userId).name("김화담").build())
                .build());

        mockMvc.perform(post("/auth/google")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"google-code\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.accessToken").value("access"))
                .andExpect(jsonPath("$.data.refreshToken").value("refresh"))
                .andExpect(jsonPath("$.data.isNewUser").value(true))
                .andExpect(jsonPath("$.data.user.id").value(userId.toString()));

        ArgumentCaptor<GoogleLoginRequest> captor = ArgumentCaptor.forClass(GoogleLoginRequest.class);
        verify(authService).googleLogin(captor.capture());
        assertThat(captor.getValue().getCode()).isEqualTo("google-code");
    }

    @Test
    void 인가_코드가_없으면_검증_오류다() throws Exception {
        mockMvc.perform(post("/auth/google")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\" \"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));

        verifyNoInteractions(authService);
    }

    @Test
    void 같은_이메일로_가입한_계정이_있으면_409다() throws Exception {
        given(authService.googleLogin(any())).willThrow(new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS));

        mockMvc.perform(post("/auth/google")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"google-code\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("EMAIL_ALREADY_EXISTS"));
    }
}
