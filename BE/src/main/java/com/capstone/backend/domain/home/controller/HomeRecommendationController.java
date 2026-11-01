package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.service.HomeRecommendationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/home/recommendations")
@RequiredArgsConstructor
@Tag(name = "13. Home", description = "홈 맞춤 추천 API")
public class HomeRecommendationController {

    private final HomeRecommendationService homeRecommendationService;

    @Operation(
            summary = "환경 기반 추천 조회",
            description = "비어 있는 환경 조건을 채울 제품 추천. 서버가 하루 한 번 미리 계산해 둔 결과를 돌려준다. " +
                    "state: READY(권할 제품 있음), FULLY_COVERED('지금 루틴으로 충분해요'), NOT_READY('준비 중'). " +
                    "NOT_READY 면 result 와 computedAt 이 null 이다. result 는 추천 결과 조회와 같은 형식이고 items[].badges 에 ENV 근거가 있다. " +
                    "missingConditions, coveredConditions 는 결과에 조건이 아직 실리지 않았으면 빈 배열이다. " +
                    "지역을 설정하지 않았으면 404 REGION_NOT_SET."
    )
    @GetMapping("/environment")
    public ResponseEntity<ApiResponse<EnvironmentRecommendationResponse>> getEnvironment(
            @AuthenticationPrincipal UUID userId) {
        return ResponseEntity.ok(ApiResponse.success(homeRecommendationService.getEnvironment(userId)));
    }
}
