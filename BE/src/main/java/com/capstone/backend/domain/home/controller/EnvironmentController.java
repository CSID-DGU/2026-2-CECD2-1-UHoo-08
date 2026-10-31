package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse;
import com.capstone.backend.domain.home.service.EnvironmentService;
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
@RequestMapping("/environment")
@RequiredArgsConstructor
@Tag(name = "12. Environment", description = "생활 환경 API")
public class EnvironmentController {

    private final EnvironmentService environmentService;

    @Operation(
            summary = "환경 요약 조회",
            description = "사용자 지역의 최근 4주(오늘 포함 28일) 환경과, 그 환경이 요구하는 제품 조건을 지금 루틴이 채우는지 돌려준다. " +
                    "관측이 없는 날은 세지 않고 dayCount 는 관측이 있는 날 수다. " +
                    "seasonChange 는 최근 7일 평균 습도가 3주 전 7일보다 15%p 이상 다를 때만 있다. " +
                    "conditions 는 홈 환경 추천 결과에서 읽고, 아직 없으면 빈 배열이다. covered=false 인 것만 '비어 있어요'로 표시하고 개수는 missingCount 를 쓴다. " +
                    "기록이 하나도 없으면 updatedAt 과 stats.avgHumidity 가 null 이다. 지역을 설정하지 않았으면 404 REGION_NOT_SET."
    )
    @GetMapping("/summary")
    public ResponseEntity<ApiResponse<EnvironmentSummaryResponse>> getSummary(@AuthenticationPrincipal UUID userId) {
        return ResponseEntity.ok(ApiResponse.success(environmentService.getSummary(userId)));
    }
}
