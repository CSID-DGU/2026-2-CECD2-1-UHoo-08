package com.capstone.backend.domain.auth.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.auth.dto.OAuthUserInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class KakaoOAuthService {

    private final WebClient webClient;

    @Value("${kakao.client-id}")
    private String kakaoClientId;

    @Value("${kakao.client-secret:}")
    private String kakaoClientSecret;

    @Value("${kakao.redirect-uri}")
    private String kakaoRedirectUri;

    /**
     * 인가 코드(code) → access_token 교환 → 사용자 정보 조회
     */
    public OAuthUserInfo getUserInfo(String code) {
        String accessToken = exchangeCodeForToken(code);
        return fetchUserInfo(accessToken);
    }

    private String exchangeCodeForToken(String code) {
        // MultiValueMap 사용 → Spring이 URL 인코딩 자동 처리
        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.add("grant_type", "authorization_code");
        formData.add("client_id", kakaoClientId);
        formData.add("redirect_uri", kakaoRedirectUri);
        formData.add("code", code);
        if (kakaoClientSecret != null && !kakaoClientSecret.isBlank()) {
            formData.add("client_secret", kakaoClientSecret);
        }

        log.info("[Kakao] token exchange 요청: client_id={}, redirect_uri={}", kakaoClientId, kakaoRedirectUri);

        try {
            Map<String, Object> response = webClient.post()
                    .uri("https://kauth.kakao.com/oauth/token")
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(BodyInserters.fromFormData(formData))
                    .retrieve()
                    .onStatus(
                            status -> status.is4xxClientError() || status.is5xxServerError(),
                            clientResponse -> clientResponse.bodyToMono(String.class)
                                    .flatMap(errorBody -> {
                                        log.error("[Kakao] token exchange 실패: status={}, body={}",
                                                clientResponse.statusCode(), errorBody);
                                        return Mono.error(new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN));
                                    })
                    )
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();

            String accessToken = (String) response.get("access_token");
            if (accessToken == null) {
                log.error("[Kakao] access_token 없음. 응답: {}", response);
                throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
            }

            log.info("[Kakao] token exchange 성공");
            return accessToken;

        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("[Kakao] token exchange 예외: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        }
    }

    @SuppressWarnings("unchecked")
    private OAuthUserInfo fetchUserInfo(String accessToken) {
        try {
            Map<String, Object> response = webClient.post()
                    .uri("https://kapi.kakao.com/v2/user/me")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken)
                    .retrieve()
                    .onStatus(
                            status -> status.is4xxClientError() || status.is5xxServerError(),
                            clientResponse -> clientResponse.bodyToMono(String.class)
                                    .flatMap(errorBody -> {
                                        log.error("[Kakao] user/me 실패: status={}, body={}",
                                                clientResponse.statusCode(), errorBody);
                                        return Mono.error(new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN));
                                    })
                    )
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();

            log.info("[Kakao] user/me 응답 keys: {}", response.keySet());

            Object rawId = response.get("id");
            String providerId = rawId instanceof Number
                    ? String.valueOf(((Number) rawId).longValue())
                    : String.valueOf(rawId);

            String name = "카카오 사용자";
            String email = null;

            // kakao_account가 있으면 우선 사용 (이메일·프로필 동의 시)
            Map<String, Object> kakaoAccount = (Map<String, Object>) response.get("kakao_account");
            if (kakaoAccount != null) {
                Map<String, Object> profile = (Map<String, Object>) kakaoAccount.get("profile");
                if (profile != null) {
                    name = (String) profile.getOrDefault("nickname", name);
                }
                email = (String) kakaoAccount.get("email");
            } else {
                // kakao_account 없으면 properties 사용 (기본 닉네임)
                Map<String, Object> properties = (Map<String, Object>) response.get("properties");
                if (properties != null) {
                    name = (String) properties.getOrDefault("nickname", name);
                }
                log.warn("[Kakao] kakao_account 없음 → properties 사용. 카카오 개발자센터에서 '이메일' 동의항목 확인 필요");
            }

            log.info("[Kakao] user/me 성공: providerId={}, name={}", providerId, name);
            return new OAuthUserInfo(providerId, name, email);

        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("[Kakao] user/me 예외: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        }
    }
}
