package com.capstone.backend.domain.auth.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JwtUtil;
import com.capstone.backend.domain.auth.dto.GoogleLoginRequest;
import com.capstone.backend.domain.auth.dto.SocialLoginRequest;
import com.capstone.backend.domain.auth.dto.TokenResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final String GOOGLE = "GOOGLE";

    private final UserRepository userRepository;
    private final JwtUtil jwtUtil;
    private final OAuthService oAuthService;
    private final GoogleOAuthService googleOAuthService;

    @Transactional
    public TokenResponse socialLogin(SocialLoginRequest request) {
        OAuthService.OAuthUserInfo info = oAuthService.getKakaoUserInfo(request.getCode());

        boolean[] isNewUser = {false};

        User user = userRepository
                .findByProviderAndProviderId("KAKAO", info.getProviderId())
                .orElseGet(() -> {
                    isNewUser[0] = true;
                    return userRepository.save(User.builder()
                            .email(info.getEmail())
                            .name(info.getName())
                            .provider("KAKAO")
                            .providerId(info.getProviderId())
                            .fcmToken(request.getFcmToken())
                            .build());
                });

        if (request.getFcmToken() != null) {
            user.updateFcmToken(request.getFcmToken());
        }

        return buildTokenResponse(user, isNewUser[0]);
    }

    /**
     * 구글 인가 코드로 로그인한다. 처음 오는 구글 계정이면 사용자를 만든다.
     *
     * 같은 이메일로 다른 방식(카카오 등)으로 가입한 계정이 있으면 EMAIL_ALREADY_EXISTS 를 낸다.
     */
    @Transactional
    public TokenResponse googleLogin(GoogleLoginRequest request) {
        OAuthService.OAuthUserInfo info = googleOAuthService.getUserInfo(request.getCode());

        Optional<User> existing = userRepository.findByProviderAndProviderId(GOOGLE, info.getProviderId());
        if (existing.isPresent()) {
            return buildTokenResponse(existing.get(), false);
        }

        if (info.getEmail() != null && userRepository.existsByEmail(info.getEmail())) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }

        User user = userRepository.save(User.builder()
                .email(info.getEmail())
                .name(info.getName())
                .provider(GOOGLE)
                .providerId(info.getProviderId())
                .build());
        return buildTokenResponse(user, true);
    }

    @Transactional(readOnly = true)
    public TokenResponse refreshToken(String refreshToken) {
        if (!jwtUtil.validateToken(refreshToken)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED);
        }

        UUID userId = jwtUtil.getUserId(refreshToken);
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        return buildTokenResponse(user, false);
    }

    private TokenResponse buildTokenResponse(User user, boolean isNewUser) {
        return TokenResponse.builder()
                .accessToken(jwtUtil.generateAccessToken(user.getId()))
                .refreshToken(jwtUtil.generateRefreshToken(user.getId()))
                .isNewUser(isNewUser)
                .user(TokenResponse.UserInfo.from(user))
                .build();
    }
}
