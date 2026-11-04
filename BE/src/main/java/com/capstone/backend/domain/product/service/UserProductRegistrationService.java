package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * 보유 제품을 등록하고 이미 쓰는 제품과의 충돌을 함께 돌려준다.
 *
 * 등록의 트랜잭션이 끝난 뒤 궁합을 확인하려고 등록과 나눠 두었다. AI 호출은 오래 걸릴 수 있어 DB 연결을 붙잡으면 안 된다.
 * 트랜잭션을 걸지 않는다. 궁합 확인에 실패해도 등록은 그대로 성공한다.
 */
@Service
@RequiredArgsConstructor
public class UserProductRegistrationService {

    private final UserProductService userProductService;
    private final CompatibilityService compatibilityService;

    public UserProductCreateResponse create(UUID userId, UserProductCreateRequest request) {
        UserProductCreateResponse created = userProductService.create(userId, request);
        return created.withConflicts(compatibilityService.conflictsOf(userId, created.getProductId()));
    }
}
