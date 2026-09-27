package com.capstone.backend.domain.recommendation.entity;

/**
 * 추천 job 의 상태.
 *
 * PENDING → IN_PROGRESS → (NEEDS_CLARIFICATION) → COMPLETED | FAILED
 *
 * {@code recommendation_jobs.status} 에 문자열로 저장된다. 지금까지 각 서비스가
 * {@code "COMPLETED".equals(...)} 처럼 문자열을 직접 비교해 왔는데, 오타가 나면
 * 조건이 조용히 false 가 되어 완료된 job 을 미완료로 읽는다.
 */
public enum JobStatus {

    PENDING,
    IN_PROGRESS,

    /**
     * 되묻는 중이라 사용자의 답을 기다리는 상태.
     *
     * <p>실패가 아니다. 이 상태의 job 을 정리하면 답을 받아도 이어 돌릴 수 없다.
     */
    NEEDS_CLARIFICATION,

    COMPLETED,
    FAILED;

    /** 더 진행되지 않는 상태인가. */
    public boolean isFinal() {
        return this == COMPLETED || this == FAILED;
    }

    /** 저장된 문자열이 이 상태인가. 알 수 없는 값이면 false 다. */
    public boolean matches(String raw) {
        return name().equals(raw);
    }
}
