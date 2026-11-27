package com.capstone.backend.domain.preference.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.preference.dto.response.PreferenceChangeRevertResponse;
import com.capstone.backend.domain.preference.service.PreferenceWeightChangeService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Collections;
import java.util.UUID;

import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class PreferenceWeightControllerTest {

    private static final String REVERT_PATH = "/users/me/preference-weights/changes/{changeId}/revert";

    @Mock
    PreferenceWeightChangeService preferenceWeightChangeService;
    @InjectMocks
    PreferenceWeightController controller;

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
    void 되돌리면_200과_변경_ID_되돌림_여부를_돌려준다() throws Exception {
        UUID changeId = UUID.randomUUID();
        given(preferenceWeightChangeService.revert(userId, changeId))
                .willReturn(new PreferenceChangeRevertResponse(changeId, true));

        mockMvc.perform(post(REVERT_PATH, changeId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.changeId").value(changeId.toString()))
                .andExpect(jsonPath("$.data.reverted").value(true));
    }

    @Test
    void 이미_되돌렸으면_409_CHANGE_NOT_REVERTIBLE이다() throws Exception {
        UUID changeId = UUID.randomUUID();
        given(preferenceWeightChangeService.revert(userId, changeId))
                .willThrow(new BusinessException(ErrorCode.CHANGE_NOT_REVERTIBLE));

        mockMvc.perform(post(REVERT_PATH, changeId))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("CHANGE_NOT_REVERTIBLE"));
    }

    @Test
    void 남의_변경이면_404_NOT_FOUND다() throws Exception {
        UUID changeId = UUID.randomUUID();
        given(preferenceWeightChangeService.revert(userId, changeId))
                .willThrow(new BusinessException(ErrorCode.NOT_FOUND));

        mockMvc.perform(post(REVERT_PATH, changeId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }

    @Test
    void 변경_ID가_UUID가_아니면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post(REVERT_PATH, "chg_88"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(preferenceWeightChangeService);
    }
}
