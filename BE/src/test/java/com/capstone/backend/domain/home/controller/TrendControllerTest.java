package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.exception.GlobalExceptionHandler;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse;
import com.capstone.backend.domain.home.service.TrendService;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TrendControllerTest {

    @Mock
    TrendService trendService;
    @InjectMocks
    TrendController controller;

    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                // 앱 설정(spring.jackson.serialization.write-dates-as-timestamps: false)과 같게 날짜를 문자열로 쓴다
                .setMessageConverters(new MappingJackson2HttpMessageConverter(Jackson2ObjectMapperBuilder.json()
                        .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build()))
                .build();
    }

    @Test
    void 요즘_뜨는_제품은_기간_순위별_제품_갱신_시각을_내리고_개수_기본값은_10이다() throws Exception {
        UUID productId = UUID.randomUUID();
        given(trendService.getProducts(10)).willReturn(new TrendProductsResponse(30, List.of(
                new TrendProductsResponse.Item(1, productId, "베어 워터 쿠션", "ROMAND", 28000, "https://img/cushion.png", 38),
                new TrendProductsResponse.Item(2, UUID.randomUUID(), "쥬시 래스팅 틴트", "ROMAND", 13000, null, null)),
                OffsetDateTime.of(2026, 9, 20, 4, 0, 0, 0, ZoneOffset.UTC)));

        mockMvc.perform(get("/trends/products"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.periodDays").value(30))
                .andExpect(jsonPath("$.data.items[0].rank").value(1))
                .andExpect(jsonPath("$.data.items[0].productId").value(productId.toString()))
                .andExpect(jsonPath("$.data.items[0].name").value("베어 워터 쿠션"))
                .andExpect(jsonPath("$.data.items[0].price").value(28000))
                .andExpect(jsonPath("$.data.items[0].interestChangePct").value(38))
                .andExpect(content().string(containsString("\"interestChangePct\":null")))
                .andExpect(jsonPath("$.data.updatedAt").value("2026-09-20T04:00:00Z"));
    }

    @Test
    void 개수를_주면_그만큼_읽고_기록이_없으면_빈_목록이다() throws Exception {
        given(trendService.getProducts(5)).willReturn(new TrendProductsResponse(30, List.of(), null));

        mockMvc.perform(get("/trends/products").param("limit", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.items").isEmpty())
                .andExpect(content().string(containsString("\"updatedAt\":null")));
    }

    @Test
    void 개수가_범위_밖이거나_숫자가_아니면_422_VALIDATION_ERROR다() throws Exception {
        given(trendService.getProducts(21)).willThrow(new BusinessException(ErrorCode.VALIDATION_ERROR));

        mockMvc.perform(get("/trends/products").param("limit", "21"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
        mockMvc.perform(get("/trends/products").param("limit", "many"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
    }
}
