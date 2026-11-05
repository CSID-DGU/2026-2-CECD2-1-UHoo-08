package com.capstone.backend.domain.recommendation.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

/** 세트 제품 교체 결과. 결과 조회의 bundles[] 원소와 같은 모양이다 */
@Getter
@AllArgsConstructor
public class BundleSwapResponse {
    private RecommendationResultV2Response.Bundle bundle;
}
