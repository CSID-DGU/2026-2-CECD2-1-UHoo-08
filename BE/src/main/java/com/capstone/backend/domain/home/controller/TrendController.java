package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse;
import com.capstone.backend.domain.home.service.TrendService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/trends")
@RequiredArgsConstructor
@Tag(name = "10. Home & Environment", description = "홈 맞춤 추천, 생활 환경, 트렌드 API")
public class TrendController {

    private final TrendService trendService;

    @Operation(
            summary = "요즘 뜨는 제품 조회",
            description = "인플루언서 언급으로 계산한 최근 30일(오늘 포함) 인기 상승 제품. 개인화하지 않은 전체 공통 순위다. " +
                    "순위는 최근 30일 트렌드 지수 합 순이고, interestChangePct 는 직전 30일 합보다 몇 % 늘었는지다(줄었으면 음수). " +
                    "직전 30일 기록이 없으면 interestChangePct 는 null 이다. price 는 최저가, 없으면 정가다. " +
                    "기록이 없으면 items 는 빈 배열이고 updatedAt 은 null 이다. limit 는 기본 10, 1~20 밖이면 422 VALIDATION_ERROR."
    )
    @GetMapping("/products")
    public ResponseEntity<ApiResponse<TrendProductsResponse>> getProducts(
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(ApiResponse.success(trendService.getProducts(limit)));
    }
}
