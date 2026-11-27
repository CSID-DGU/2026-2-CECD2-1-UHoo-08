package com.capstone.backend.domain.auth.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

/** 카카오, 구글에서 가져온 사용자 정보. 로그인 서비스가 가입, 조회에 쓴다 */
@Getter
@AllArgsConstructor
public class OAuthUserInfo {
    private String providerId;
    private String name;
    private String email;
}
