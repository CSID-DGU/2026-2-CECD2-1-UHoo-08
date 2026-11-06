package com.capstone.backend.domain.recommendation.enums;

/**
 * 추천 job 의 상태.
 *
 * PENDING → IN_PROGRESS → (NEEDS_CLARIFICATION) → COMPLETED | FAILED
 *
 * {@code recommendation_jobs.status} 에 이름 그대로 저장되고 Recommendation.status 가 이 enum 으로 매핑한다.
 * 문자열로 비교하면 오타가 나도 조건이 조용히 false 가 되어 완료된 job 을 미완료로 읽는다.
 * AI 도 같은 다섯 값만 쓴다. 다른 값이 들어오면 BE 가 그 행을 읽지 못하므로 값을 늘릴 때는 AI 와 함께 바꾼다.
 */
public enum JobStatus {

    PENDING,
    IN_PROGRESS,

    /**
     * 되묻는 중이라 사용자의 답을 기다리는 상태.
     *
     * 실패가 아니다. 이 상태의 job 을 정리하면 답을 받아도 이어 돌릴 수 없다.
     */
    NEEDS_CLARIFICATION,

    COMPLETED,
    FAILED;

    /** 더 진행되지 않는 상태인가. */
    public boolean isFinal() {
        return this == COMPLETED || this == FAILED;
    }
}
