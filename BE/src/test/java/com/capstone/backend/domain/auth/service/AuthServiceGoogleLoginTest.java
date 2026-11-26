package com.capstone.backend.domain.auth.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JwtUtil;
import com.capstone.backend.domain.auth.dto.GoogleLoginRequest;
import com.capstone.backend.domain.auth.dto.OAuthUserInfo;
import com.capstone.backend.domain.auth.dto.TokenResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class AuthServiceGoogleLoginTest {

    @Mock
    UserRepository userRepository;
    @Mock
    JwtUtil jwtUtil;
    @Mock
    KakaoOAuthService kakaoOAuthService;
    @Mock
    GoogleOAuthService googleOAuthService;
    @InjectMocks
    AuthService authService;

    private final UUID userId = UUID.randomUUID();
    private final GoogleLoginRequest request = new GoogleLoginRequest("google-code");

    private void googleReturns(String email) {
        given(googleOAuthService.getUserInfo("google-code"))
                .willReturn(new OAuthUserInfo("google-sub", "김화담", email));
    }

    private void tokensIssued() {
        given(jwtUtil.generateAccessToken(userId)).willReturn("access");
        given(jwtUtil.generateRefreshToken(userId)).willReturn("refresh");
    }

    private User user(String provider, String email) {
        return User.builder()
                .id(userId)
                .name("김화담")
                .email(email)
                .provider(provider)
                .providerId("google-sub")
                .build();
    }

    @Test
    void 처음_오는_구글_계정이면_가입시키고_새_사용자로_돌려준다() {
        googleReturns("hwadam@gmail.com");
        given(userRepository.findByProviderAndProviderId("GOOGLE", "google-sub")).willReturn(Optional.empty());
        given(userRepository.existsByEmail("hwadam@gmail.com")).willReturn(false);
        given(userRepository.save(any(User.class))).willReturn(user("GOOGLE", "hwadam@gmail.com"));
        tokensIssued();

        TokenResponse response = authService.googleLogin(request);

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        assertThat(saved.getValue().getProvider()).isEqualTo("GOOGLE");
        assertThat(saved.getValue().getProviderId()).isEqualTo("google-sub");
        assertThat(saved.getValue().getName()).isEqualTo("김화담");
        assertThat(saved.getValue().getEmail()).isEqualTo("hwadam@gmail.com");
        assertThat(saved.getValue().getFcmToken()).isNull();

        assertThat(response.isNewUser()).isTrue();
        assertThat(response.getAccessToken()).isEqualTo("access");
        assertThat(response.getRefreshToken()).isEqualTo("refresh");
        assertThat(response.getUser().getId()).isEqualTo(userId);
    }

    @Test
    void 이미_가입한_구글_계정이면_새로_만들지_않고_로그인시킨다() {
        googleReturns("hwadam@gmail.com");
        given(userRepository.findByProviderAndProviderId("GOOGLE", "google-sub"))
                .willReturn(Optional.of(user("GOOGLE", "hwadam@gmail.com")));
        tokensIssued();

        TokenResponse response = authService.googleLogin(request);

        assertThat(response.isNewUser()).isFalse();
        assertThat(response.getUser().getId()).isEqualTo(userId);
        verify(userRepository, never()).existsByEmail(any());
        verify(userRepository, never()).save(any());
    }

    @Test
    void 같은_이메일로_다른_방식으로_가입한_계정이_있으면_막는다() {
        googleReturns("hwadam@gmail.com");
        given(userRepository.findByProviderAndProviderId("GOOGLE", "google-sub")).willReturn(Optional.empty());
        given(userRepository.existsByEmail("hwadam@gmail.com")).willReturn(true);

        assertThatThrownBy(() -> authService.googleLogin(request))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.EMAIL_ALREADY_EXISTS);
        verify(userRepository, never()).save(any());
        verifyNoInteractions(jwtUtil);
    }

    @Test
    void 이메일이_없으면_중복_검사_없이_가입시킨다() {
        googleReturns(null);
        given(userRepository.findByProviderAndProviderId("GOOGLE", "google-sub")).willReturn(Optional.empty());
        given(userRepository.save(any(User.class))).willReturn(user("GOOGLE", null));
        tokensIssued();

        TokenResponse response = authService.googleLogin(request);

        assertThat(response.isNewUser()).isTrue();
        verify(userRepository, never()).existsByEmail(any());
    }

    @Test
    void 구글_인증이_실패하면_사용자를_조회하지_않는다() {
        given(googleOAuthService.getUserInfo("google-code"))
                .willThrow(new BusinessException(ErrorCode.INVALID_OAUTH_TOKEN));

        assertThatThrownBy(() -> authService.googleLogin(request))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.INVALID_OAUTH_TOKEN);
        verifyNoInteractions(userRepository, jwtUtil);
    }
}
