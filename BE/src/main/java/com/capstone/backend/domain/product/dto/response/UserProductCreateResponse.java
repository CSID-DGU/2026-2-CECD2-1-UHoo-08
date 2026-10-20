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
    /** 이미 쓰는 제품과 같이 쓰면 안 되는 조합. 성분 궁합 확인이 연결되기 전까지 빈 배열 */
    private List<Conflict> conflicts;

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
