package com.capstone.backend.domain.preference.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.preference.dto.response.PreferenceChangeRevertResponse;
import com.capstone.backend.domain.preference.service.PreferenceWeightChangeService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/users/me/preference-weights")
@RequiredArgsConstructor
@Tag(name = "11. Preference Weights", description = "개인화 가중치 API")
public class PreferenceWeightController {

    private final PreferenceWeightChangeService preferenceWeightChangeService;

    @Operation(
            summary = "가중치 변경 되돌리기",
            description = "피드백이나 자주 고른 조건으로 바뀐 가중치 한 건을 되돌린다. " +
                    "결과 보고서의 되돌리기(appliedPreference.changeId)와 마이페이지에서 부른다. " +
                    "되돌린 표시만 남기고, 가중치는 AI 가 되돌리지 않은 변경만 합쳐 비동기로 다시 계산한다. " +
                    "이미 되돌렸으면 409 CHANGE_NOT_REVERTIBLE, 내 변경이 아니면 404 NOT_FOUND."
    )
    @PostMapping("/changes/{changeId}/revert")
    public ResponseEntity<ApiResponse<PreferenceChangeRevertResponse>> revert(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID changeId) {
        return ResponseEntity.ok(ApiResponse.success(preferenceWeightChangeService.revert(userId, changeId)));
    }
}
