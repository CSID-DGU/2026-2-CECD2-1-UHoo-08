package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse.Pair;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse.Schedule;
import com.capstone.backend.domain.product.service.CompatibilityService;
import com.capstone.backend.domain.product.service.ProductRecognizeService;
import com.capstone.backend.domain.product.service.ProductService;
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
import java.util.List;
import java.util.UUID;

import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class ProductControllerCompatibilityTest {

    @Mock
    ProductService productService;
    @Mock
    ProductRecognizeService productRecognizeService;
    @Mock
    CompatibilityService compatibilityService;
    @InjectMocks
    ProductController controller;

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(userId, null, Collections.emptyList()));
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
                .build();
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void 판정과_쌍을_명세_모양으로_내려보낸다() throws Exception {
        UUID userProductId = UUID.randomUUID();
        given(compatibilityService.check(userId, productId)).willReturn(new ProductCompatibilityResponse(
                CompatibilityLevel.SEPARATE, "지금 쓰시는 제품 1개와 시간대를 나눠 쓰세요",
                List.of(new Pair(userProductId, "레티놀 앰플", "AHA", "레티놀", CompatibilityLevel.SEPARATE,
                        "AHA와 레티놀은 시간대를 나눠 쓰세요", "저녁에 나눠 쓰세요", new Schedule(null, null, "하루 걸러 쓰세요"))),
                List.of("근거")));

        mockMvc.perform(get("/products/{productId}/compatibility", productId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.level").value("SEPARATE"))
                .andExpect(jsonPath("$.data.bannerText").value("지금 쓰시는 제품 1개와 시간대를 나눠 쓰세요"))
                .andExpect(jsonPath("$.data.pairs[0].userProductId").value(userProductId.toString()))
                .andExpect(jsonPath("$.data.pairs[0].userProductName").value("레티놀 앰플"))
                .andExpect(jsonPath("$.data.pairs[0].ingredientA").value("AHA"))
                .andExpect(jsonPath("$.data.pairs[0].ingredientB").value("레티놀"))
                .andExpect(jsonPath("$.data.pairs[0].level").value("SEPARATE"))
                .andExpect(jsonPath("$.data.pairs[0].title").value("AHA와 레티놀은 시간대를 나눠 쓰세요"))
                .andExpect(jsonPath("$.data.pairs[0].reason").value("저녁에 나눠 쓰세요"))
                .andExpect(jsonPath("$.data.pairs[0].schedule.tip").value("하루 걸러 쓰세요"))
                .andExpect(jsonPath("$.data.basis[0]").value("근거"));
    }

    @Test
    void 없는_상품이면_404다() throws Exception {
        given(compatibilityService.check(userId, productId)).willThrow(new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        mockMvc.perform(get("/products/{productId}/compatibility", productId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error.code").value("PRODUCT_NOT_FOUND"));
    }
}
