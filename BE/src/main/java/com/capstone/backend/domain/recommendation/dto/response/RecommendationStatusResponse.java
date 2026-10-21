package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.entity.Recommendation;
import lombok.Builder;
import lombok.Getter;

import java.util.UUID;

@Getter
@Builder
public class RecommendationStatusResponse {
    private UUID jobId;
    private String status;
    private String step;
    private Integer progress;

    public static RecommendationStatusResponse from(Recommendation r) {
        return RecommendationStatusResponse.builder()
                .jobId(r.getId())
                .status(r.getStatus().name())
                .step(r.getStep())
                .progress(r.getProgress())
                .build();
    }
}
