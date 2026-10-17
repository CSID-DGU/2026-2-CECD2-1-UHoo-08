package com.capstone.backend.domain.home.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Immutable;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 제품별 하루 트렌드 지수(product_trend_daily). 키는 (product_id, date) 다.
 *
 * AI 가 인플루언서 언급을 모아 쓰고 BE 는 읽기만 한다. 홈의 요즘 뜨는 제품이 읽는다.
 */
@Entity
@Immutable
@Table(name = "product_trend_daily")
@IdClass(ProductTrendDaily.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ProductTrendDaily {

    @Id
    @Column(name = "product_id")
    private UUID productId;

    @Id
    @Column(name = "date")
    private LocalDate date;

    @Column(name = "mention_count", nullable = false)
    private int mentionCount;

    /** 광고 게시물의 언급. 실제 반응과 구분하려고 따로 센다 */
    @Column(name = "ad_mention_count", nullable = false)
    private int adMentionCount;

    @Column(name = "engagement", nullable = false)
    private int engagement;

    @Column(name = "trend_score")
    private Float trendScore;

    /** 어떤 계산식으로 나온 값인지 */
    @Column(name = "formula_version", length = 20)
    private String formulaVersion;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private UUID productId;
        private LocalDate date;
    }
}
