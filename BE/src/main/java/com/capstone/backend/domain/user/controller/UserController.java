package com.capstone.backend.domain.user.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.user.dto.request.PreferencesRequest;
import com.capstone.backend.domain.user.dto.request.PreferenceUpdateRequest;
import com.capstone.backend.domain.user.dto.request.RegionUpdateRequest;
import com.capstone.backend.domain.user.dto.request.SkinProfileUpdateRequest;
import com.capstone.backend.domain.user.dto.response.PreferenceResponse;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.RegionResponse;
import com.capstone.backend.domain.user.dto.response.SkinProfileResponse;
import com.capstone.backend.domain.user.dto.response.UserMeResponse;
import com.capstone.backend.domain.user.service.UserProfileService;
import com.capstone.backend.domain.user.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequiredArgsConstructor
@Tag(name = "2. User", description = "사용자 API")
public class UserController {

    private final UserService userService;
    private final UserProfileService userProfileService;

    @Operation(summary = "내 정보 조회")
    @GetMapping("/users/profile")
    public ResponseEntity<ApiResponse<UserMeResponse>> getMyInfo(
            @AuthenticationPrincipal UUID userId) {
        return ResponseEntity.ok(ApiResponse.success(userService.getMyInfo(userId)));
    }

    @Operation(summary = "프로필 설정/수정")
    @PatchMapping(value = "/users/profile", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<ProfileUpdateResponse>> updateMyProfile(
            @AuthenticationPrincipal UUID userId,
            @RequestPart(value = "name", required = false) String name,
            @RequestPart(value = "gender", required = false) String gender,
            @RequestPart(value = "image", required = false) MultipartFile image) {
        return ResponseEntity.ok(ApiResponse.success(userService.updateMyProfile(userId, name, gender, image)));
    }

    @Operation(summary = "피부 정보 수정")
    @PatchMapping("/users/me/skin-profile")
    public ResponseEntity<ApiResponse<SkinProfileResponse>> updateSkinProfile(
            @AuthenticationPrincipal UUID userId,
            @RequestBody SkinProfileUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.success(userProfileService.updateSkinProfile(userId, request)));
    }

    @Operation(summary = "선호 정보 저장 (최초)")
    @PostMapping("/users/me/preferences")
    public ResponseEntity<ApiResponse<PreferenceResponse>> savePreferences(
            @AuthenticationPrincipal UUID userId,
            @RequestBody PreferencesRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(userProfileService.savePreferences(userId, request)));
    }

    @Operation(summary = "선호 정보 수정")
    @PatchMapping("/users/me/preferences")
    public ResponseEntity<ApiResponse<PreferenceResponse>> updatePreferences(
            @AuthenticationPrincipal UUID userId,
            @RequestBody PreferenceUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.success(userProfileService.updatePreferences(userId, request)));
    }

    @Operation(
            summary = "사용자 지역 설정",
            description = "생활 환경을 계산할 지역을 저장한다. 환경 데이터가 시·도 단위라 regionCode 는 시·도 이름이다: " +
                    "서울, 부산, 대구, 인천, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남광주, 경북, 경남, 제주. " +
                    "광주와 전남은 전남광주 하나로 다룬다. regionName 은 화면 표시용 이름(예: 고양시 덕양구)으로 50자까지. " +
                    "지원하지 않는 지역이거나 값이 비었으면 422 VALIDATION_ERROR."
    )
    @PatchMapping("/users/me/region")
    public ResponseEntity<ApiResponse<RegionResponse>> updateRegion(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody RegionUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.success(userService.updateRegion(userId, request)));
    }
}
