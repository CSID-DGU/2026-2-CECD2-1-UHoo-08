package com.capstone.backend.domain.product.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 사진 등록의 중간 결과(photo_recognitions).
 *
 * 제품명 사진 인식 → 기한 사진 인식 → 보유 제품 등록으로 이어지는 요청들을 이 행 하나로 잇는다.
 * expiresAt 이 지나면 쓸 수 없고, 정리 배치가 지운다.
 */
@Entity
@Table(name = "photo_recognitions")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class PhotoRecognition {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id")
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "name_image_url", nullable = false, columnDefinition = "text")
    private String nameImageUrl;

    @Column(name = "date_image_url", columnDefinition = "text")
    private String dateImageUrl;

    /** 제품명 사진에서 읽은 글자 */
    @Column(name = "read_text", columnDefinition = "text")
    private String readText;

    /** 제품 후보 목록(jsonb 배열) */
    @Type(JsonType.class)
    @Builder.Default
    @Column(name = "candidates", nullable = false, columnDefinition = "jsonb")
    private String candidates = "[]";

    /** 기한 사진에서 읽은 값(jsonb). {expiryDate, paoMonths, manufacturedAt} */
    @Type(JsonType.class)
    @Column(name = "expiry_result", columnDefinition = "jsonb")
    private String expiryResult;

    /** AI 응답 원본(jsonb). 등록할 때 user_products.recognized_raw 로 옮긴다 */
    @Type(JsonType.class)
    @Column(name = "raw", columnDefinition = "jsonb")
    private String raw;

    @Column(name = "expires_at", nullable = false)
    private OffsetDateTime expiresAt;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    /** 내 인식 결과이고 아직 만료되지 않았는지 */
    public boolean isUsableBy(UUID userId, OffsetDateTime now) {
        return this.userId.equals(userId) && this.expiresAt.isAfter(now);
    }

    /** 기한 사진 인식 결과를 남긴다. 다시 찍으면 덮어쓴다 */
    public void recordExpiry(String dateImageUrl, String expiryResult, String raw) {
        this.dateImageUrl = dateImageUrl;
        this.expiryResult = expiryResult;
        this.raw = raw;
    }
}
