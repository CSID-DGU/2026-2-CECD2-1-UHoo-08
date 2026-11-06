package com.capstone.backend.domain.home.dto.request;

import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.UUID;

/** 홈 카드 수동 생성 요청 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
public class HomeRunAdminRequest {

    @NotNull(message = "userId는 필수입니다.")
    private UUID userId;

    @NotNull(message = "kind는 필수입니다.")
    private HomeRecommendationKind kind;
}
