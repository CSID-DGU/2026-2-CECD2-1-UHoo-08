package com.capstone.backend.domain.recommendation.dto.request;

import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.TargetPersonalColor;
import com.capstone.backend.domain.recommendation.enums.TargetRelation;
import com.capstone.backend.domain.recommendation.enums.TargetSkinConcern;
import com.capstone.backend.domain.recommendation.enums.TargetSkinType;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

/** 자연어 추천 요청. 값이 정해진 항목은 enum 으로 받아, 목록에 없는 값이면 요청 오류가 된다 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RecommendationQueryRequest {

    @NotBlank(message = "query는 필수입니다.")
    private String query;

    /** 없으면 SELF */
    private RecommendationBasis basis;

    /** basis=OTHER 일 때 쓰실 분 정보. 모든 필드 선택 */
    @Valid
    private TargetProfile targetProfile;

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
