package com.capstone.backend.domain.auth.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.auth.dto.OAuthUserInfo;
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
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.Map;

/**
 * 구글 인가 코드로 구글 사용자 정보를 가져온다.
 *
 * 인가 코드를 구글 access token 으로 바꾼 뒤 userinfo 를 조회한다. FE 는 scope 에 openid, email, profile 을 넣어 인가 코드를 받아야 한다.
 */
@Slf4j
@Service
public class GoogleOAuthService {

    static final String TOKEN_URL = "https://oauth2.googleapis.com/token";
    static final String USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo";
    static final String DEFAULT_NAME = "구글 사용자";

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE = new ParameterizedTypeReference<>() {};

    private final WebClient webClient;
    private final String clientId;
    private final String clientSecret;
    private final String redirectUri;

    public GoogleOAuthService(WebClient webClient,
                              @Value("${google.client-id:}") String clientId,
                              @Value("${google.client-secret:}") String clientSecret,
                              @Value("${google.redirect-uri:}") String redirectUri) {
        this.webClient = webClient;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.redirectUri = redirectUri;
    }

    public OAuthUserInfo getUserInfo(String code) {
        if (isBlank(clientId) || isBlank(clientSecret) || isBlank(redirectUri)) {
            log.error("[Google] OAuth 설정이 비어 있습니다. GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI 를 확인하세요");
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
        String accessToken = exchangeCodeForToken(code);
        return fetchUserInfo(accessToken);
    }

    private String exchangeCodeForToken(String code) {
        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.add("grant_type", "authorization_code");
        formData.add("client_id", clientId);
        formData.add("client_secret", clientSecret);
        formData.add("redirect_uri", redirectUri);
        formData.add("code", code);

        Map<String, Object> response = call("token exchange", webClient.post()
                .uri(TOKEN_URL)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData(formData)));

        Object accessToken = response.get("access_token");
        if (!(accessToken instanceof String token) || token.isBlank()) {
            log.error("[Google] 토큰 응답에 access_token 이 없습니다");
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        }
        return token;
    }

    private OAuthUserInfo fetchUserInfo(String accessToken) {
        Map<String, Object> response = call("userinfo", webClient.get()
                .uri(USER_INFO_URL)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken));

        Object sub = response.get("sub");
        if (!(sub instanceof String providerId) || providerId.isBlank()) {
            log.error("[Google] userinfo 응답에 sub 가 없습니다");
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        }

        String name = response.get("name") instanceof String n && !n.isBlank() ? n : DEFAULT_NAME;

        // 구글이 확인한 이메일만 저장한다
        String email = Boolean.TRUE.equals(response.get("email_verified")) && response.get("email") instanceof String e
                ? e
                : null;

        log.info("[Google] userinfo 성공: providerId={}", providerId);
        return new OAuthUserInfo(providerId, name, email);
    }

    /** 구글 API 를 부르고 JSON 응답을 돌려준다. 응답이 실패나 빈 값이면 INVALID_OAUTH_TOKEN */
    private Map<String, Object> call(String step, WebClient.RequestHeadersSpec<?> request) {
        try {
            Map<String, Object> response = request.retrieve().bodyToMono(MAP_TYPE).block();
            if (response == null) {
                log.error("[Google] {} 응답이 비어 있습니다", step);
                throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
            }
            return response;
        } catch (BusinessException e) {
            throw e;
        } catch (WebClientResponseException e) {
            log.error("[Google] {} 실패: status={}, body={}", step, e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        } catch (Exception e) {
            log.error("[Google] {} 예외: {}", step, e.getMessage(), e);
            throw new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN);
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
