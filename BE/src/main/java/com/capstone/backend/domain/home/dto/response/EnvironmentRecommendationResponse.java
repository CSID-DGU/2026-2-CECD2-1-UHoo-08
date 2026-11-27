package com.capstone.backend.domain.home.dto.response;

import com.capstone.backend.domain.home.enums.HomeRecommendationState;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.OffsetDateTime;
import java.util.List;

/** 비어 있는 환경 조건을 채울 제품 추천. AI 홈 배치가 하루 한 번 미리 계산해 둔 결과다 */
@Getter
@AllArgsConstructor
public class EnvironmentRecommendationResponse {
    private HomeRecommendationState state;
    /** 보유 제품이 채우지 못한 조건 */
    private List<MissingCondition> missingConditions;
    /** 보유 제품이 이미 채운 조건 */
    private List<CoveredCondition> coveredConditions;
    /** 추천 결과 조회와 같은 모양. 아직 계산 전이면 null */
    private RecommendationResultV2Response result;
    /** 계산한 시각. 아직 계산 전이면 null */
    private OffsetDateTime computedAt;

    @Getter
    @AllArgsConstructor
    public static class MissingCondition {
        /** UV_PROTECT, SOOTHING, BARRIER */
        private String key;
        private String label;
    }

    @Getter
    @AllArgsConstructor
    public static class CoveredCondition {
        private String key;
        private String label;
        /** 채우는 보유 제품 */
        private String coveredBy;
    }
}
