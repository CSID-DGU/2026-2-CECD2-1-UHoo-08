package com.capstone.backend.domain.product.dto.response;

import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

/** 이 제품을 지금 쓰는 제품들과 함께 써도 되는지 */
@Getter
@AllArgsConstructor
public class ProductCompatibilityResponse {
    /** 가장 심한 판정 */
    private CompatibilityLevel level;
    /** 상세 배너 문구. OK 면 null */
    private String bannerText;
    /** 같이 쓰지 말 것 → 시간 나눠 쓸 것 순 */
    private List<Pair> pairs;
    /** 판단 근거 문구 */
    private List<String> basis;

    @Getter
    @AllArgsConstructor
    public static class Pair {
        private UUID userProductId;
        private String userProductName;
        /** 이 제품 성분 */
        private String ingredientA;
        /** 보유 제품 성분 */
        private String ingredientB;
        /** SEPARATE, AVOID */
        private CompatibilityLevel level;
        private String title;
        private String reason;
        /** 시간대 안내. AI 가 주지 않으면 null */
        private Schedule schedule;
    }

    @Getter
    @AllArgsConstructor
    public static class Schedule {
        /** AI 가 문구 하나만 주므로 지금은 null */
        private String morning;
        /** AI 가 문구 하나만 주므로 지금은 null */
        private String evening;
        private String tip;
    }
}
