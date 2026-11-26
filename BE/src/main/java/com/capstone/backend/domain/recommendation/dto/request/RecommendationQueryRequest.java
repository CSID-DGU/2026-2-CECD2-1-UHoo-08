package com.capstone.backend.domain.recommendation.dto.request;

import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.TargetPersonalColor;
import com.capstone.backend.domain.recommendation.enums.TargetRelation;
import com.capstone.backend.domain.recommendation.enums.TargetSkinConcern;
import com.capstone.backend.domain.recommendation.enums.TargetSkinType;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

/** 자연어 추천 요청. 값이 정해진 항목은 enum 으로 받아, 목록에 없는 값이면 요청 오류가 된다 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RecommendationQueryRequest {

    /** 검색창 문장. baseProductId 가 있으면 비어도 된다 */
    private String query;

    /** 상품 상세에서 이 상품을 기준으로 추천받을 때의 상품. 있으면 AI 가 문장을 해석하지 않고 평가 경로로 간다 */
    private UUID baseProductId;

    /** 없으면 SELF */
    private RecommendationBasis basis;

    /** basis=OTHER 일 때 쓰실 분 정보. 모든 필드 선택 */
    @Valid
    private TargetProfile targetProfile;

    @JsonIgnore
    @AssertTrue(message = "query와 baseProductId 중 하나는 있어야 합니다.")
    public boolean isQueryOrBaseProductGiven() {
        return hasQuery() || baseProductId != null;
    }

    public boolean hasQuery() {
        return query != null && !query.isBlank();
    }

    public RecommendationBasis basisOrDefault() {
        return basis != null ? basis : RecommendationBasis.SELF;
    }

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class TargetProfile {
        private TargetRelation relation;
        private TargetPersonalColor personalColor;
        private TargetSkinType skinType;
        private List<TargetSkinConcern> skinConcerns;
    }
}
