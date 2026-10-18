package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse.Candidate;
import com.capstone.backend.domain.product.service.PhotoRecognitionService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class UserProductControllerTest {

    @Mock
    PhotoRecognitionService photoRecognitionService;
    @InjectMocks
    UserProductController controller;

    MockMvc mockMvc;

    private final UUID userId = UUID.randomUUID();
    private final MockMultipartFile image = new MockMultipartFile("image", "front.jpg", "image/jpeg", new byte[]{1});

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
    void 제품명_사진을_올리면_인식ID와_후보를_돌려준다() throws Exception {
        UUID recognitionId = UUID.randomUUID();
        given(photoRecognitionService.recognizeName(eq(userId), any())).willReturn(new PhotoRecognitionResponse(
                recognitionId, "innisfree GREEN TEA SEED SERUM 80ml",
                List.of(new Candidate("p-1", "그린티 씨드 세럼", "이니스프리", null, "https://img/1", 96))));

        mockMvc.perform(multipart("/user-products/recognitions").file(image))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.recognitionId").value(recognitionId.toString()))
                .andExpect(jsonPath("$.data.readText").value("innisfree GREEN TEA SEED SERUM 80ml"))
                .andExpect(jsonPath("$.data.candidates[0].productId").value("p-1"))
                .andExpect(jsonPath("$.data.candidates[0].matchScore").value(96))
                // 명세상 nullable 이지만 키는 있어야 한다. jsonPath 의 exists 는 null 을 없는 것으로 보므로 본문으로 확인한다
                .andExpect(content().string(containsString("\"volume\":null")));
    }

    @Test
    void 후보가_없어도_200이다() throws Exception {
        given(photoRecognitionService.recognizeName(eq(userId), any()))
                .willReturn(new PhotoRecognitionResponse(UUID.randomUUID(), "", List.of()));

        mockMvc.perform(multipart("/user-products/recognitions").file(image))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.candidates").isEmpty());
    }

    @Test
    void 사진이_없으면_422_VALIDATION_ERROR다() throws Exception {
        given(photoRecognitionService.recognizeName(eq(userId), isNull()))
                .willThrow(new BusinessException(ErrorCode.VALIDATION_ERROR));

        mockMvc.perform(multipart("/user-products/recognitions"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
    }

    @Test
    void 용량을_넘으면_413_FILE_TOO_LARGE다() throws Exception {
        given(photoRecognitionService.recognizeName(eq(userId), any()))
                .willThrow(new BusinessException(ErrorCode.FILE_TOO_LARGE));

        mockMvc.perform(multipart("/user-products/recognitions").file(image))
                .andExpect(status().isPayloadTooLarge())
                .andExpect(jsonPath("$.error.code").value("FILE_TOO_LARGE"));
    }

    @Test
    void AI_인식에_실패하면_422_IMAGE_PARSE_FAILED다() throws Exception {
        given(photoRecognitionService.recognizeName(eq(userId), any()))
                .willThrow(new BusinessException(ErrorCode.IMAGE_PARSE_FAILED));

        mockMvc.perform(multipart("/user-products/recognitions").file(image))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("IMAGE_PARSE_FAILED"));
    }
}
