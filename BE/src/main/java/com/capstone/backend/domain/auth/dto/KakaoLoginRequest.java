package com.capstone.backend.domain.auth.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class KakaoLoginRequest {

    @NotBlank(message = "code는 필수입니다.")
    private String code;      // 카카오 인가 코드 (authorization code)

    private String fcmToken;
}
