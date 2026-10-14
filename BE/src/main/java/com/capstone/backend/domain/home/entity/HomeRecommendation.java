package com.capstone.backend.domain.home.entity;

import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.Type;

import java.io.Serializable;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 홈 맞춤 추천 카드의 하루 계산 결과(home_recommendations). 키는 (user_id, kind) 다.
 *
 * AI 홈 배치가 매일 덮어쓰고 BE 는 읽기만 한다.
 * 행이 없는 것(아직 안 돌았다)과 result 의 항목이 비어 있는 것(돌았는데 권할 게 없다)은 화면에서 다르게 보여야 한다.
 */
@Entity
@Immutable
@Table(name = "home_recommendations")
@IdClass(HomeRecommendation.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class HomeRecommendation {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    @Id
    @Enumerated(EnumType.STRING)
    @Column(name = "kind", length = 20)
    private HomeRecommendationKind kind;

    /** 추천 결과(jsonb). AI contracts/result.py 와 같은 모양이다 */
    @Type(JsonType.class)
    @Column(name = "result", nullable = false, columnDefinition = "jsonb")
    private String result;

    /** 이 카드를 만든 실행 */
    @Column(name = "job_id")
    private UUID jobId;

    @Column(name = "generated_at", nullable = false)
    private OffsetDateTime generatedAt;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private UUID userId;
        private HomeRecommendationKind kind;
    }
}
