package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.response.ExpiryRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.ExpiryRecognitionResponse.ReadValue;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse.Candidate;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.enums.RegistrationSource;
import com.capstone.backend.domain.product.service.PhotoRecognitionService;
import com.capstone.backend.domain.product.service.UserProductService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class UserProductControllerTest {

    @Mock
    PhotoRecognitionService photoRecognitionService;
    @Mock
    UserProductService userProductService;
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
    // 기한 사진 인식

    @Test
    void 기한_사진을_올리면_세_항목을_value와_status로_돌려준다() throws Exception {
        UUID recognitionId = UUID.randomUUID();
        given(photoRecognitionService.recognizeExpiry(eq(userId), eq(recognitionId), any())).willReturn(
                new ExpiryRecognitionResponse(ReadValue.of("2027-04-18"), ReadValue.of(12), ReadValue.of(null)));

        mockMvc.perform(multipart("/user-products/recognitions/{id}/expiry", recognitionId).file(image))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.expiryDate.value").value("2027-04-18"))
                .andExpect(jsonPath("$.data.expiryDate.status").value("READ"))
                .andExpect(jsonPath("$.data.paoMonths.value").value(12))
                .andExpect(jsonPath("$.data.paoMonths.status").value("READ"))
                .andExpect(jsonPath("$.data.manufacturedAt.status").value("NOT_READ"))
                .andExpect(content().string(containsString("\"manufacturedAt\":{\"value\":null")));
    }

    @Test
    void 인식_결과가_없거나_만료됐으면_404_RECOGNITION_NOT_FOUND다() throws Exception {
        UUID recognitionId = UUID.randomUUID();
        given(photoRecognitionService.recognizeExpiry(eq(userId), eq(recognitionId), any()))
                .willThrow(new BusinessException(ErrorCode.RECOGNITION_NOT_FOUND));

        mockMvc.perform(multipart("/user-products/recognitions/{id}/expiry", recognitionId).file(image))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("RECOGNITION_NOT_FOUND"));
    }

    @Test
    void 인식ID_형식이_틀리면_404_RECOGNITION_NOT_FOUND다() throws Exception {
        mockMvc.perform(multipart("/user-products/recognitions/{id}/expiry", "rc_5f1a").file(image))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("RECOGNITION_NOT_FOUND"));
        verifyNoInteractions(photoRecognitionService);
    }

    @Test
    void 기한_사진이_10MB를_넘으면_413_FILE_TOO_LARGE다() throws Exception {
        UUID recognitionId = UUID.randomUUID();
        given(photoRecognitionService.recognizeExpiry(eq(userId), eq(recognitionId), any()))
                .willThrow(new BusinessException(ErrorCode.FILE_TOO_LARGE));

        mockMvc.perform(multipart("/user-products/recognitions/{id}/expiry", recognitionId).file(image))
                .andExpect(status().isPayloadTooLarge())
                .andExpect(jsonPath("$.error.code").value("FILE_TOO_LARGE"));
    }
    // 보유 제품 등록

    @Test
    void 보유_제품을_등록하면_201과_등록_결과를_돌려준다() throws Exception {
        UUID productId = UUID.randomUUID();
        UUID userProductId = UUID.randomUUID();
        ArgumentCaptor<UserProductCreateRequest> request = ArgumentCaptor.forClass(UserProductCreateRequest.class);
        given(userProductService.create(eq(userId), request.capture()))
                .willReturn(new UserProductCreateResponse(userProductId, productId, "그린티 씨드 세럼", List.of()));

        mockMvc.perform(post("/user-products")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"productId":"%s","recognitionId":"%s","openedAt":"2026-09-20",
                                 "expiryDate":"2027-04-18","paoMonths":12,"manufacturedAt":null,
                                 "remainingPct":70,"storageLocation":"VANITY","source":"PHOTO"}
                                """.formatted(productId, UUID.randomUUID())))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.userProductId").value(userProductId.toString()))
                .andExpect(jsonPath("$.data.productId").value(productId.toString()))
                .andExpect(jsonPath("$.data.name").value("그린티 씨드 세럼"))
                .andExpect(jsonPath("$.data.conflicts").isArray())
                .andExpect(jsonPath("$.data.conflicts").isEmpty());

        // 보관 위치는 받지 않고 무시한다
        assertThat(request.getValue().getOpenedAt()).isEqualTo(LocalDate.of(2026, 9, 20));
        assertThat(request.getValue().getPaoMonths()).isEqualTo(12);
        assertThat(request.getValue().getSource()).isEqualTo(RegistrationSource.PHOTO);
    }

    @Test
    void 남은_양이_0에서_100을_벗어나면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/user-products")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"productId":"%s","remainingPct":120,"source":"MANUAL"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(userProductService);
    }

    @Test
    void 등록_경로가_PHOTO나_MANUAL이_아니면_422_VALIDATION_ERROR다() throws Exception {
        mockMvc.perform(post("/user-products")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"productId":"%s","remainingPct":70,"source":"KIOSK"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(userProductService);
    }

    @Test
    void 같은_제품을_이미_쓰는_중이면_409_ALREADY_REGISTERED다() throws Exception {
        given(userProductService.create(eq(userId), any()))
                .willThrow(new BusinessException(ErrorCode.ALREADY_REGISTERED));

        mockMvc.perform(post("/user-products")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"productId":"%s","remainingPct":70,"source":"MANUAL"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error.code").value("ALREADY_REGISTERED"));
    }

    @Test
    void 없는_제품이면_404_PRODUCT_NOT_FOUND다() throws Exception {
        given(userProductService.create(eq(userId), any()))
                .willThrow(new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        mockMvc.perform(post("/user-products")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"productId":"%s","remainingPct":70,"source":"MANUAL"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("PRODUCT_NOT_FOUND"));
        verify(userProductService).create(eq(userId), any());
    }
}
