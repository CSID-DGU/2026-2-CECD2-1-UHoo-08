package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
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
@RequestMapping("/home")
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
    @GetMapping("/recommendations/environment")
    public ResponseEntity<ApiResponse<EnvironmentRecommendationResponse>> getEnvironment(
            @AuthenticationPrincipal UUID userId) {
        return ResponseEntity.ok(ApiResponse.success(homeRecommendationService.getEnvironment(userId)));
    }

    @Operation(
            summary = "내 루틴 점검 조회",
            description = "쓰는 제품끼리 성분 충돌을 검사한 결과와, 같이 쓰면 안 되는 쌍의 대체 추천. 서버가 하루 한 번 미리 계산해 둔 결과다. " +
                    "checked=false 면 아직 점검 전이라 쌍과 개수가 비어 있으니 '준비 중'으로 보여 준다. " +
                    "점검 뒤에 다 쓰거나 지운 제품이 결과에 있으면 지난 결과라 checked=false 로 내리고, 다음 점검에서 다시 채워진다. " +
                    "productCount 는 쓰는 중인 보유 제품 수다. pairs 는 AVOID → SEPARATE → OK 순이고, 보유 제품이 2개 미만이면 pairs 는 빈 배열, counts 는 0, replacement 는 null 이다. " +
                    "홈 카드는 counts 와 pairs 중 level=AVOID 첫 번째만 쓴다. 성분 정보가 없어 빠진 제품은 uncomparedCount 로 안내한다."
    )
    @GetMapping("/routine-check")
    public ResponseEntity<ApiResponse<RoutineCheckResponse>> getRoutineCheck(@AuthenticationPrincipal UUID userId) {
        return ResponseEntity.ok(ApiResponse.success(homeRecommendationService.getRoutineCheck(userId)));
    }
}
