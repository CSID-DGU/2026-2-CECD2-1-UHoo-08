package com.capstone.backend.domain.home.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.home.dto.request.HomeRunAdminRequest;
import com.capstone.backend.domain.home.service.HomeAdminService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/admin/home")
@RequiredArgsConstructor
@Tag(name = "15. Admin", description = "관리자 API")
public class HomeAdminController {

    private final HomeAdminService homeAdminService;

    @Operation(
            summary = "홈 카드 수동 생성",
            description = "시연과 디버깅용. 일일 배치의 대상 조건을 보지 않고 이 사용자의 홈 카드 생성을 AI 에 바로 요청하고 202 를 돌려준다. " +
                    "kind: ROUTINE, ENV. 관리자가 아니면 403 FORBIDDEN, 없는 사용자면 404 NOT_FOUND."
    )
    @PostMapping("/run")
    public ResponseEntity<ApiResponse<Void>> run(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody HomeRunAdminRequest request) {
        homeAdminService.requestCard(userId, request.getUserId(), request.getKind());
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResponse.success(null));
    }
}
