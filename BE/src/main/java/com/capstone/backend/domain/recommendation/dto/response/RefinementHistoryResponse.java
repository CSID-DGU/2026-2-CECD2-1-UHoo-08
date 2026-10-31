package com.capstone.backend.domain.recommendation.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

/** 처음 검색부터 지금까지의 조건 수정 단계 */
@Getter
@AllArgsConstructor
public class RefinementHistoryResponse {
    /** 오래된 순 */
    private List<Step> steps;
    /** 개인화 제안. 제안 API 를 만들지 않아 항상 null */
    private Suggestion suggestion;

    @Getter
    @AllArgsConstructor
    public static class Step {
        private UUID jobId;
        /** "처음 검색" 또는 "+ 더 저렴하게" */
        private String label;
        /** 처음 검색이면 검색 문장, 나머지는 직전 단계와 달라진 조건 */
        private String detail;
        private int candidateCount;
        /** 지금 보고 있는 단계 */
        @JsonProperty("isCurrent")
        private boolean current;
    }

    @Getter
    @AllArgsConstructor
    public static class Suggestion {
        private String suggestionId;
        private String title;
        private String message;
    }
}
