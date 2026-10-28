package com.capstone.backend.domain.recommendation.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 질의와 그 해석 결과(search_logs). 라우터 정확도를 실사용 기준으로 보기 위한 기록이다.
 */
@Entity
@Table(name = "search_logs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class SearchLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 탈퇴하면 DB 가 NULL 로 바꾼다. 질의 분포는 남긴다 */
    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "job_id")
    private UUID jobId;

    @Column(name = "raw_query", nullable = false, columnDefinition = "text")
    private String rawQuery;

    /** 라우터가 고른 경로. 비어 있으면 해석 단계에서 멈춘 질의다 */
    @Column(name = "scenario", length = 20)
    private String scenario;

    @Type(JsonType.class)
    @Column(name = "query_spec", columnDefinition = "jsonb")
    private String querySpec;

    @Column(name = "confidence")
    private Float confidence;

    /** 되물어서 답을 받은 질의인가 */
    @Builder.Default
    @Column(name = "clarified", nullable = false)
    private boolean clarified = false;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    /** 아직 해석 결과를 남기지 않았는지. job 이 처음 끝난 상태가 될 때 한 번만 채운다 */
    public boolean isInterpretationEmpty() {
        return scenario == null && querySpec == null && confidence == null;
    }

    /** 라우터가 고른 경로와 해석 결과를 남긴다 */
    public void recordInterpretation(String scenario, String querySpec, Float confidence) {
        this.scenario = scenario;
        this.querySpec = querySpec;
        this.confidence = confidence;
    }

    /** 되물어서 답을 받았다 */
    public void markClarified() {
        this.clarified = true;
    }
}
