package com.capstone.backend.domain.recommendation.repository;

import com.capstone.backend.domain.recommendation.entity.RecommendationFeedback;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.UUID;

public interface RecommendationFeedbackRepository extends JpaRepository<RecommendationFeedback, Long> {

    /**
     * 같은 결과의 같은 제품에 대한 피드백을 한 줄로 남기고 그 id 를 돌려준다. 이미 있으면 반응과 이유를 덮어쓴다.
     * 덮어쓸 때 가중치 반영 시각을 비워 AI 가 바뀐 피드백을 다시 반영하게 한다.
     * 유니크 제약으로 충돌을 처리하므로, 같은 피드백이 동시에 와도 오류 없이 한 줄만 남는다.
     *
     * @param reasonTags PostgreSQL 배열 문자열. 예: "{TOO_EXPENSIVE,BAD_REVIEWS}"
     */
    @Query(value = """
            INSERT INTO recommendation_feedback (job_id, user_id, product_id, vote, reason_tags)
            VALUES (:jobId, :userId, :productId, :vote, CAST(:reasonTags AS text[]))
            ON CONFLICT (job_id, product_id, user_id)
            DO UPDATE SET vote = EXCLUDED.vote, reason_tags = EXCLUDED.reason_tags, applied_at = NULL
            RETURNING id
            """, nativeQuery = true)
    Long upsert(@Param("jobId") UUID jobId, @Param("userId") UUID userId, @Param("productId") UUID productId,
                @Param("vote") String vote, @Param("reasonTags") String reasonTags);
}
