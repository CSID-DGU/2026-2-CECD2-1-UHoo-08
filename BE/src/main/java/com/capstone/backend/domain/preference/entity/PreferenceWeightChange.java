package com.capstone.backend.domain.preference.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 가중치를 움직인 사건 하나(preference_weight_changes).
 *
 * 행은 AI 의 피드백 반영 처리만 만든다. 가중치 계산 규칙을 한곳에 두기 위해서다.
 * BE 는 읽고, 사용자가 되돌릴 때 revertedAt 만 채운다. 그래서 revertedAt 말고는 insert·update 에서 빠진다.
 */
@Entity
@Table(name = "preference_weight_changes")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PreferenceWeightChange {

    @Id
    @Column(name = "id", insertable = false, updatable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false, insertable = false, updatable = false)
    private UUID userId;

    /** FEEDBACK | REFINE_PATTERN */
    @Column(name = "source", nullable = false, length = 20, insertable = false, updatable = false)
    private String source;

    /** FEEDBACK 이면 recommendation_feedback.id, REFINE_PATTERN 이면 패턴 키(CHEAPER 등) */
    @Column(name = "source_ref", columnDefinition = "text", insertable = false, updatable = false)
    private String sourceRef;

    /** 점수 항목별 변화량(jsonb). 예: {"budget_fit": 0.05} */
    @Type(JsonType.class)
    @Column(name = "deltas", nullable = false, columnDefinition = "jsonb", insertable = false, updatable = false)
    private String deltas;

    /** 화면에 보여 줄 문장 */
    @Column(name = "text", nullable = false, columnDefinition = "text", insertable = false, updatable = false)
    private String text;

    /** 사용자가 되돌린 시각. NULL 이면 아직 반영된 상태다 */
    @Column(name = "reverted_at")
    private OffsetDateTime revertedAt;

    @Column(name = "created_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime createdAt;

    /** 되돌린 시각을 남긴다. 이 엔티티에서 BE 가 바꿀 수 있는 값은 이것뿐이다 */
    public void revert(OffsetDateTime now) {
        this.revertedAt = now;
    }
}
