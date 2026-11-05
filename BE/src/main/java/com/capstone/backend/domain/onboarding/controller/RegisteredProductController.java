package com.capstone.backend.domain.onboarding.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductBatchRequest;
import com.capstone.backend.domain.onboarding.service.RegisteredProductService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/onboarding/favorites/items")
@RequiredArgsConstructor
@Tag(name = "3. Onboarding", description = "온보딩 API")
public class RegisteredProductController {

    private final RegisteredProductService registeredProductService;

    @Operation(
            summary = "온보딩 제품 일괄 등록",
            description = "온보딩 완료 시 localStorage의 제품 UUID 목록을 registered_products + user_products에 저장."
    )
    @PostMapping("/batch")
    public ResponseEntity<ApiResponse<Integer>> saveBatch(
            @AuthenticationPrincipal UUID userId,
            @RequestBody RegisteredProductBatchRequest request) {
        int saved = registeredProductService.saveBatch(userId, request);
        return ResponseEntity.ok(ApiResponse.success(saved));
    }
}
