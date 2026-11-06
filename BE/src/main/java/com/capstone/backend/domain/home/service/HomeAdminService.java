package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.HomeRunRequest;
import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.UUID;

/** 시연과 디버깅을 위한 홈 카드 수동 생성. 일일 배치의 대상 조건을 보지 않고 바로 요청한다 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HomeAdminService {

    private final HwadamProperties hwadamProperties;
    private final UserRepository userRepository;
    private final AiInternalClient aiInternalClient;

    /** 관리자가 아니면 FORBIDDEN, 없는 사용자면 NOT_FOUND. 사용자가 있는지 알려 주지 않도록 권한을 먼저 본다 */
    public void requestCard(UUID adminId, UUID userId, HomeRecommendationKind kind) {
        if (!hwadamProperties.getAdmin().getUserIds().contains(adminId)) {
            throw new BusinessException(ErrorCode.FORBIDDEN);
        }
        if (!userRepository.existsById(userId)) {
            throw new BusinessException(ErrorCode.NOT_FOUND);
        }
        log.info("[HomeAdmin] 홈 카드 수동 생성 요청: adminId={}, userId={}, kind={}", adminId, userId, kind);
        aiInternalClient.runHome(new HomeRunRequest(userId.toString(), kind.name()));
    }
}
