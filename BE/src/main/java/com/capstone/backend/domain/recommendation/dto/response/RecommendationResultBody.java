package com.capstone.backend.domain.recommendation.dto.response;

/**
 * 추천 결과 조회 응답. 상품 기준 추천(v1) job 은 {@link RecommendationResultResponse}, 자연어 추천 job 은
 * {@link RecommendationResultV2Response} 로 내린다. 같은 경로가 두 모양을 내리므로 둘을 묶는다.
 */
public interface RecommendationResultBody {
}
