package com.capstone.backend.domain.auth.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.auth.dto.GoogleLoginRequest;
import com.capstone.backend.domain.auth.dto.SocialLoginRequest;
import com.capstone.backend.domain.auth.dto.TokenRefreshRequest;
import com.capstone.backend.domain.auth.dto.TokenResponse;
import com.capstone.backend.domain.auth.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
@Tag(name = "1. Auth", description = "인증 API")
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "카카오 소셜 로그인")
    @PostMapping("/social")
    public ResponseEntity<ApiResponse<TokenResponse>> socialLogin(@Valid @RequestBody SocialLoginRequest request) {
        return ResponseEntity.ok(ApiResponse.success(authService.socialLogin(request)));
    }

    @Operation(summary = "구글 소셜 로그인",
            description = "구글 인가 코드로 로그인합니다. 처음 오는 구글 계정이면 가입하고 isNewUser 를 true 로 돌려줍니다. "
                    + "같은 이메일로 다른 방식으로 가입한 계정이 있으면 409 EMAIL_ALREADY_EXISTS 입니다.")
    @PostMapping("/google")
    public ResponseEntity<ApiResponse<TokenResponse>> googleLogin(@Valid @RequestBody GoogleLoginRequest request) {
        return ResponseEntity.ok(ApiResponse.success(authService.googleLogin(request)));
    }

    @Operation(summary = "토큰 재발급")
    @PostMapping("/token/refresh")
    public ResponseEntity<ApiResponse<TokenResponse>> refreshToken(
            @Valid @RequestBody TokenRefreshRequest request) {
        return ResponseEntity.ok(ApiResponse.success(authService.refreshToken(request.getRefreshToken())));
    }
}
