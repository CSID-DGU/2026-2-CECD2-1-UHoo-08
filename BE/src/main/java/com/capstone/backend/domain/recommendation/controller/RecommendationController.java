package com.capstone.backend.domain.recommendation.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.recommendation.dto.request.ProductSearchRequest;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationRequest;
import com.capstone.backend.domain.recommendation.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationJobResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService;
import com.capstone.backend.domain.recommendation.service.RecommendationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/recommendations")
@RequiredArgsConstructor
@Tag(name = "8. Recommendation", description = "제품 추천 API")
public class RecommendationController {

    private final RecommendationService recommendationService;
    private final RecommendationJobService recommendationJobService;

    @Operation(
            summary = "자연어 추천 요청",
            description = "검색창 문장으로 추천 job 을 만들고 202 로 jobId 를 바로 돌려준다. 진행은 statusUrl 로 폴링한다. " +
                    "basis: SELF(기본, 내 피부), POPULAR(전체 인기), OTHER(다른 사람, targetProfile 함께). " +
                    "SELF 인데 피부 정보가 없으면 404 SKIN_PROFILE_NOT_FOUND. " +
                    "POST /recommendations/search(동기)를 대체한다."
    )
    @PostMapping("/queries")
    public ResponseEntity<ApiResponse<RecommendationQueryResponse>> requestQuery(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody RecommendationQueryRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(recommendationJobService.requestQuery(userId, request)));
    }

    @Operation(summary = "자연어 제품 검색", description = "검색창 자연어 입력 → FastAPI 벡터 검색 → 결과 반환 (동기)")
    @PostMapping("/search")
    public ResponseEntity<ApiResponse<ProductSearchResponse>> searchProducts(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody ProductSearchRequest request) {
        return ResponseEntity.ok(ApiResponse.success(
                recommendationService.searchProducts(userId, request.getQuery())));
    }

    @Operation(summary = "제품 추천 요청", description = "비동기 처리. 즉시 jobId 반환 후 status 폴링으로 완료 확인.")
    @PostMapping
    public ResponseEntity<ApiResponse<RecommendationJobResponse>> requestRecommendation(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody RecommendationRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(recommendationService.requestRecommendation(userId, request)));
    }

    @Operation(summary = "추천 상태 폴링", description = "status가 COMPLETED가 되면 GET /{jobId} 호출")
    @GetMapping("/{jobId}/status")
    public ResponseEntity<ApiResponse<RecommendationStatusResponse>> getStatus(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID jobId) {
        return ResponseEntity.ok(ApiResponse.success(recommendationService.getStatus(userId, jobId)));
    }

    @Operation(summary = "추천 결과 조회", description = "status=COMPLETED 확인 후 1회 호출")
    @GetMapping("/{jobId}")
    public ResponseEntity<ApiResponse<RecommendationResultResponse>> getResult(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID jobId) {
        return ResponseEntity.ok(ApiResponse.success(recommendationService.getResult(userId, jobId)));
    }
}
