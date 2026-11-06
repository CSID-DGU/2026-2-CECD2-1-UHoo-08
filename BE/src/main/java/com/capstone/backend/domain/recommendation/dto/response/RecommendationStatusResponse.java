package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.entity.Recommendation;
import lombok.Getter;

import java.util.UUID;

/** 추천 진행 상태. 상품 기준 추천(v1) job 은 이 모양 그대로 내리고, 자연어 추천 job 은 {@link RecommendationStatusV2Response} 로 필드를 더한다 */
@Getter
public class RecommendationStatusResponse {
    private final UUID jobId;
    private final String status;
    /** 현재 단계 문구 */
    private final String step;
    private final Integer progress;

    protected RecommendationStatusResponse(Recommendation r) {
        this.jobId = r.getId();
        this.status = r.getStatus().name();
        this.step = r.getStep();
        this.progress = r.getProgress();
    }

    public static RecommendationStatusResponse from(Recommendation r) {
        return new RecommendationStatusResponse(r);
    }
}
