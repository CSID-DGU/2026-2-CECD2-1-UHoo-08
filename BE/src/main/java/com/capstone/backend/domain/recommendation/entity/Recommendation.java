package com.capstone.backend.domain.recommendation.entity;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.user.entity.User;
import io.hypersistence.utils.hibernate.type.array.StringArrayType;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "recommendation_jobs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class Recommendation {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    /**
     * 평가 기준이 되는 상품. 조건 탐색처럼 기준 상품 없이 시작하는 요청에서는 비어 있다.
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "base_product_id")
    private Product product;

    @Column(name = "search_purpose", length = 20)
    private String searchPurpose;

    @Column(name = "price_tolerance_percent")
    private Integer priceTolerancePercent;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private JobStatus status;

    @Column(name = "step", length = 50)
    private String step;

    @Column(name = "progress", nullable = false)
    private Integer progress;

    @Type(JsonType.class)
    @Column(name = "result", columnDefinition = "jsonb")
    private String result;

    @Column(name = "error_msg")
    private String errorMsg;

    // ── v2 그래프 ──────────────────────────────────────────────────
    /** 어느 경로로 돌았는지. AI graph/registry.py 의 SCENARIOS 키 */
    @Column(name = "scenario", length = 20)
    private String scenario;

    /** 원문을 해석한 조건(jsonb) */
    @Type(JsonType.class)
    @Column(name = "query_spec", columnDefinition = "jsonb")
    private String querySpec;

    /** 조건 수정이면 이어 온 부모 job. 부모가 지워지면 DB 가 NULL 로 바꾼다 */
    @Column(name = "parent_job_id")
    private UUID parentJobId;

    /** 되묻기·조건 수정에서 이어 돌리기 위한 그래프 상태(jsonb) */
    @Type(JsonType.class)
    @Column(name = "state_snapshot", columnDefinition = "jsonb")
    private String stateSnapshot;

    /** 진행 단계 목록(jsonb). [{key, label, state}]. AI 빌더가 갱신한다 */
    @Type(JsonType.class)
    @Column(name = "steps", columnDefinition = "jsonb")
    private String steps;

    // ── 조건 수정 · 원문 ───────────────────────────────────────────
    /** 조건 수정에서 고른 선택지 키. columnDefinition 은 validate 의 타입 이름 비교용이다 */
    @Type(StringArrayType.class)
    @Column(name = "refine_presets", columnDefinition = "_text")
    private String[] refinePresets;

    @Column(name = "refine_text", columnDefinition = "text")
    private String refineText;

    /** 사용자가 친 원문. querySpec 은 이것을 해석한 결과다 */
    @Column(name = "raw_query", columnDefinition = "text")
    private String rawQuery;

    @Column(name = "basis", length = 10)
    private String basis;

    @Type(JsonType.class)
    @Column(name = "target_profile", columnDefinition = "jsonb")
    private String targetProfile;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
