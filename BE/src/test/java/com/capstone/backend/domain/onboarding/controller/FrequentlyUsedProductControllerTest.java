package com.capstone.backend.domain.onboarding.controller;

import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.onboarding.service.FrequentlyUsedProductService;
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
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class FrequentlyUsedProductControllerTest {

    @Mock
    FrequentlyUsedProductService frequentlyUsedProductService;
    @InjectMocks
    FrequentlyUsedProductController controller;

    private final UUID userId = UUID.randomUUID();
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

    private static String body(int count) {
        return "{\"productIds\":[" + IntStream.range(0, count)
                .mapToObj(i -> "\"" + UUID.randomUUID() + "\"")
                .collect(Collectors.joining(",")) + "]}";
    }

    @Test
    void 제품_50개까지는_저장한다() throws Exception {
        given(frequentlyUsedProductService.saveBatch(eq(userId), any())).willReturn(50);

        mockMvc.perform(post("/onboarding/frequently-used-products/batch")
                        .contentType(MediaType.APPLICATION_JSON).content(body(50)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value(50));
    }

    @Test
    void 제품이_50개를_넘으면_VALIDATION_ERROR다() throws Exception {
        for (String path : new String[]{"/onboarding/frequently-used-products/batch", "/onboarding/favorites/items/batch"}) {
            mockMvc.perform(post(path).contentType(MediaType.APPLICATION_JSON).content(body(51)))
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        }
        verifyNoInteractions(frequentlyUsedProductService);
    }
}
