package com.capstone.backend.domain.product.entity;

import com.capstone.backend.domain.product.enums.RegistrationSource;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "user_products")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class UserProduct {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id")
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "product_id", nullable = false)
    private UUID productId;

    @Column(name = "usage_type", nullable = false, length = 20)
    private String usageType;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    // ── 보유 제품 정보 ──────────────────────────────────────────────
    @Column(name = "opened_at")
    private LocalDate openedAt;

    @Column(name = "purchased_at")
    private LocalDate purchasedAt;

    @Column(name = "expiry_date")
    private LocalDate expiryDate;

    /** 개봉 후 사용 기간(개월). openedAt 과 합쳐 실제 소진 기한을 잡는다 */
    @Column(name = "pao_months")
    private Integer paoMonths;

    /** 남은 양 0~100. DB 에 CHECK 가 있다 */
    @Column(name = "remaining_pct")
    private Integer remainingPct;

    @Column(name = "review_text", columnDefinition = "text")
    private String reviewText;

    /** 등록 경로 */
    @Enumerated(EnumType.STRING)
    @Column(name = "source", length = 20)
    private RegistrationSource source;

    /** 사진 인식 원본(jsonb). 사용자가 고친 최종값과 비교해 인식 정확도를 잰다 */
    @Type(JsonType.class)
    @Column(name = "recognized_raw", columnDefinition = "jsonb")
    private String recognizedRaw;

    @Column(name = "finished_at")
    private LocalDate finishedAt;

    @Column(name = "manufactured_at")
    private LocalDate manufacturedAt;

    /** 1~5. DB 에 CHECK 가 있다 */
    @Column(name = "rating")
    private Integer rating;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;
}
