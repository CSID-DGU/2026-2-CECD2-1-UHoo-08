package com.capstone.backend.domain.onboarding.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;
import com.capstone.backend.domain.onboarding.service.FrequentlyUsedProductService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@Slf4j
@RestController
@RequiredArgsConstructor
@Tag(name = "3. Onboarding", description = "온보딩 API")
public class FrequentlyUsedProductController {

    private final FrequentlyUsedProductService frequentlyUsedProductService;

    @Operation(
            summary = "자주 사용하는 제품 일괄 등록",
            description = "온보딩 완료 시 고른 제품 UUID 목록을 자주 사용하는 제품으로 저장한다. " +
                    "보유 제품(user_products)에는 넣지 않는다. 이미 등록했거나 없는 제품은 건너뛰고, 새로 저장한 개수를 돌려준다."
    )
    @PostMapping("/onboarding/frequently-used-products/batch")
    public ResponseEntity<ApiResponse<Integer>> saveBatch(
            @AuthenticationPrincipal UUID userId,
            @RequestBody FrequentlyUsedProductBatchRequest request) {
        return ResponseEntity.ok(ApiResponse.success(frequentlyUsedProductService.saveBatch(userId, request)));
    }

    /** FE 호출을 POST /onboarding/frequently-used-products/batch 로 옮기면 지운다 */
    @Deprecated
    @Operation(
            summary = "자주 사용하는 제품 일괄 등록 (사용 중단)",
            description = "사용 중단. POST /onboarding/frequently-used-products/batch 로 대체한다. 동작은 같다.",
            deprecated = true
    )
    @PostMapping("/onboarding/favorites/items/batch")
    public ResponseEntity<ApiResponse<Integer>> saveBatchDeprecated(
            @AuthenticationPrincipal UUID userId,
            @RequestBody FrequentlyUsedProductBatchRequest request) {
        log.warn("[Deprecated] POST /onboarding/favorites/items/batch 호출. /onboarding/frequently-used-products/batch 로 옮겨야 한다");
        return saveBatch(userId, request);
    }
}
