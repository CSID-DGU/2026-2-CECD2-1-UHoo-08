package com.capstone.backend.domain.product.entity;

import jakarta.persistence.*;
import lombok.*;

import java.io.Serializable;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 사용자가 본 제품(product_views). (user, product)당 한 줄이다.
 *
 * 볼 때마다 지우고 다시 넣지 않고 lastViewedAt 과 viewCount 만 갱신한다.
 * 갱신은 동시에 여러 번 봐도 한 줄로 합쳐지도록 리포지토리의 upsert 로만 한다.
 */
@Entity
@Table(name = "product_views")
@IdClass(ProductView.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ProductView {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    @Id
    @Column(name = "product_id")
    private UUID productId;

    @Column(name = "first_viewed_at", nullable = false)
    private OffsetDateTime firstViewedAt;

    @Column(name = "last_viewed_at", nullable = false)
    private OffsetDateTime lastViewedAt;

    @Column(name = "view_count", nullable = false)
    private int viewCount;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private UUID userId;
        private UUID productId;
    }
}
