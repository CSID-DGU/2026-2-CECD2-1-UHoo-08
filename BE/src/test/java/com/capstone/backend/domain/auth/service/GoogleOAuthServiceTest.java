package com.capstone.backend.domain.auth.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.auth.dto.OAuthUserInfo;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.codec.HttpMessageWriter;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.mock.http.client.reactive.MockClientHttpRequest;
import org.springframework.web.reactive.function.BodyInserter;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class GoogleOAuthServiceTest {

    private static final String REDIRECT_URI = "http://localhost:5173/auth/google";

    private final List<ClientRequest> requests = new ArrayList<>();

    private HttpStatus tokenStatus = HttpStatus.OK;
    private String tokenBody = "{\"access_token\":\"google-access\",\"token_type\":\"Bearer\"}";
    private HttpStatus userInfoStatus = HttpStatus.OK;
    private String userInfoBody = """
            {"sub":"1234567890","name":"김화담","email":"hwadam@gmail.com","email_verified":true}
            """;

    // 구글 대신 요청만 기록하고 주소별로 정해 둔 응답을 돌려주는 WebClient
    private final WebClient webClient = WebClient.builder()
            .exchangeFunction(request -> {
                requests.add(request);
                boolean isToken = request.url().toString().equals(GoogleOAuthService.TOKEN_URL);
                return Mono.just(ClientResponse.create(isToken ? tokenStatus : userInfoStatus)
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body(isToken ? tokenBody : userInfoBody)
                        .build());
            })
            .build();

    private GoogleOAuthService service(String clientId, String clientSecret, String redirectUri) {
        return new GoogleOAuthService(webClient, clientId, clientSecret, redirectUri);
    }

    private final GoogleOAuthService googleOAuthService = service("client-id", "client-secret", REDIRECT_URI);

    @Test
    void 인가_코드로_토큰을_받고_사용자_정보를_돌려준다() {
        OAuthUserInfo info = googleOAuthService.getUserInfo("4/auth-code");

        assertThat(info.getProviderId()).isEqualTo("1234567890");
        assertThat(info.getName()).isEqualTo("김화담");
        assertThat(info.getEmail()).isEqualTo("hwadam@gmail.com");

        assertThat(requests).hasSize(2);

        ClientRequest tokenRequest = requests.get(0);
        assertThat(tokenRequest.method()).isEqualTo(HttpMethod.POST);
        assertThat(tokenRequest.url()).isEqualTo(URI.create(GoogleOAuthService.TOKEN_URL));
        String form = URLDecoder.decode(bodyOf(tokenRequest), StandardCharsets.UTF_8);
        assertThat(form).contains(
                "grant_type=authorization_code",
                "client_id=client-id",
                "client_secret=client-secret",
                "redirect_uri=" + REDIRECT_URI,
                "code=4/auth-code");

        ClientRequest userInfoRequest = requests.get(1);
        assertThat(userInfoRequest.method()).isEqualTo(HttpMethod.GET);
        assertThat(userInfoRequest.url()).isEqualTo(URI.create(GoogleOAuthService.USER_INFO_URL));
        assertThat(userInfoRequest.headers().getFirst(HttpHeaders.AUTHORIZATION)).isEqualTo("Bearer google-access");
    }

    @Test
    void 확인되지_않은_이메일은_저장하지_않는다() {
        userInfoBody = """
                {"sub":"1234567890","name":"김화담","email":"hwadam@gmail.com","email_verified":false}
                """;

        assertThat(googleOAuthService.getUserInfo("code").getEmail()).isNull();
    }

    @Test
    void 이름이_없으면_기본_이름을_쓴다() {
        userInfoBody = "{\"sub\":\"1234567890\"}";

        OAuthUserInfo info = googleOAuthService.getUserInfo("code");

        assertThat(info.getName()).isEqualTo(GoogleOAuthService.DEFAULT_NAME);
        assertThat(info.getEmail()).isNull();
    }

    @Test
    void 토큰_교환이_실패하면_OAuth_오류를_낸다() {
        tokenStatus = HttpStatus.BAD_REQUEST;
        tokenBody = "{\"error\":\"invalid_grant\"}";

        assertOAuthError(() -> googleOAuthService.getUserInfo("expired-code"));
        assertThat(requests).hasSize(1);
    }

    @Test
    void 토큰_응답에_access_token이_없으면_OAuth_오류를_낸다() {
        tokenBody = "{\"token_type\":\"Bearer\"}";

        assertOAuthError(() -> googleOAuthService.getUserInfo("code"));
        assertThat(requests).hasSize(1);
    }

    @Test
    void 사용자_정보_조회가_실패하면_OAuth_오류를_낸다() {
        userInfoStatus = HttpStatus.UNAUTHORIZED;
        userInfoBody = "{\"error\":\"invalid_token\"}";

        assertOAuthError(() -> googleOAuthService.getUserInfo("code"));
    }

    @Test
    void 사용자_정보에_sub가_없으면_OAuth_오류를_낸다() {
        userInfoBody = "{\"name\":\"김화담\"}";

        assertOAuthError(() -> googleOAuthService.getUserInfo("code"));
    }

    @Test
    void 설정이_비어_있으면_구글을_부르지_않고_서버_오류를_낸다() {
        GoogleOAuthService unconfigured = service("", "", "");

        assertThatThrownBy(() -> unconfigured.getUserInfo("code"))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.INTERNAL_ERROR);
        assertThat(requests).isEmpty();
    }

    private static void assertOAuthError(ThrowingCallable call) {
        assertThatThrownBy(call)
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.INVALID_OAUTH_TOKEN);
    }

    /** 요청 본문을 문자열로 꺼낸다 */
    private static String bodyOf(ClientRequest request) {
        MockClientHttpRequest mock = new MockClientHttpRequest(request.method(), URI.create("/"));
        request.body().insert(mock, new BodyInserter.Context() {
            @Override
            public List<HttpMessageWriter<?>> messageWriters() {
                return ExchangeStrategies.withDefaults().messageWriters();
            }

            @Override
            public Optional<ServerHttpRequest> serverRequest() {
                return Optional.empty();
            }

            @Override
            public Map<String, Object> hints() {
                return Map.of();
            }
        }).block();
        return mock.getBodyAsString().block();
    }
}
