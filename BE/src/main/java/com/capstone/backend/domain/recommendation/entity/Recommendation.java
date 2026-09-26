package com.capstone.backend.domain.recommendation.entity;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.user.entity.User;
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

    @Column(name = "status", nullable = false, length = 20)
    private String status;

    @Column(name = "step", length = 50)
    private String step;

    @Column(name = "progress", nullable = false)
    private Integer progress;

    @Type(JsonType.class)
    @Column(name = "result", columnDefinition = "jsonb")
    private String result;

    @Column(name = "error_msg")
    private String errorMsg;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
