package com.capstone.backend.domain.product.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

@Getter
@AllArgsConstructor
public class UserProductCreateResponse {
    private UUID userProductId;
    private UUID productId;
    private String name;
    /** 이미 쓰는 제품과 충돌하는 조합. 보유 제품당 가장 심한 하나이고, 궁합 확인에 실패하면 빈 배열 */
    private List<Conflict> conflicts;

    public UserProductCreateResponse withConflicts(List<Conflict> conflicts) {
        return new UserProductCreateResponse(userProductId, productId, name, conflicts);
    }

    @Getter
    @AllArgsConstructor
    public static class Conflict {
        private UUID userProductId;
        private String name;
        /** SEPARATE, AVOID */
        private String level;
        private String advice;
    }
}
