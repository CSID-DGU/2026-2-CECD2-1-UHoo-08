package com.capstone.backend.domain.preference.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 사용자별 점수 가중치(user_preference_weights). 사용자당 한 줄이다.
 *
 * AI 가 쓰고 BE 는 읽기만 한다.
 */
@Entity
@Immutable
@Table(name = "user_preference_weights")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserPreferenceWeights {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    /** 점수 항목별 가중치(jsonb). 키는 AI scorers/ 의 파일 이름과 같다 (budget_fit, review 등) */
    @Type(JsonType.class)
    @Column(name = "weights", nullable = false, columnDefinition = "jsonb")
    private String weights;

    /** 이 값이 어떤 신호 몇 번으로 만들어졌는지(jsonb). 예: {"feedback": 12, "refine": 3} */
    @Type(JsonType.class)
    @Column(name = "source_counts", nullable = false, columnDefinition = "jsonb")
    private String sourceCounts;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;
}
