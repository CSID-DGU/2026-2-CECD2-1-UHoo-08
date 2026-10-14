package com.capstone.backend.domain.recommendation.entity;

import io.hypersistence.utils.hibernate.type.array.StringArrayType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 추천 결과의 제품 하나에 대한 사용자의 반응(recommendation_feedback).
 *
 * 같은 결과의 같은 제품에는 한 줄만 남는다(job_id, product_id, user_id 유니크). 다시 누르면 그 줄을 고친다.
 * 가중치 반영은 AI 가 비동기로 하고, 반영하면 appliedAt 을 채운다.
 */
@Entity
@Table(name = "recommendation_feedback")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class RecommendationFeedback {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "job_id", nullable = false)
    private UUID jobId;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "product_id", nullable = false)
    private UUID productId;

    /** UP | DOWN */
    @Column(name = "vote", nullable = false, length = 4)
    private String vote;

    /** 왜 그렇게 눌렀는지. 이 태그가 어느 점수 항목을 보정할지 정한다 */
    @Type(StringArrayType.class)
    @Builder.Default
    @Column(name = "reason_tags", nullable = false, columnDefinition = "_text")
    private String[] reasonTags = new String[0];

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    /** AI 가 가중치에 반영한 시각. NULL 이면 아직 반영 전이다 */
    @Column(name = "applied_at")
    private OffsetDateTime appliedAt;
}
