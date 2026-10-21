package com.capstone.backend.domain.recommendation.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

/** 추천 접수 결과. 진행은 statusUrl 로 폴링한다 */
@Getter
@AllArgsConstructor
public class RecommendationQueryResponse {
    private UUID jobId;
    /** 예상 소요 시간(초) */
    private int estimatedSeconds;
    private String statusUrl;
}
