package com.capstone.backend.domain.product.dto.request;

import com.capstone.backend.domain.product.enums.RegistrationSource;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.UUID;

/** 보유 제품 등록. 보관 위치는 쓰지 않는 기능이라 받지 않는다(보내도 무시한다) */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserProductCreateRequest {

    @NotNull(message = "productId는 필수입니다.")
    private UUID productId;

    /** 사진으로 등록했으면 제품명 사진 인식에서 받은 ID */
    private String recognitionId;

    /** 개봉일. 없으면 오늘 */
    private LocalDate openedAt;

    private LocalDate expiryDate;

    @Min(value = 1, message = "paoMonths는 1 이상이어야 합니다.")
    private Integer paoMonths;

    private LocalDate manufacturedAt;

    @NotNull(message = "remainingPct는 필수입니다.")
    @Min(value = 0, message = "remainingPct는 0~100이어야 합니다.")
    @Max(value = 100, message = "remainingPct는 0~100이어야 합니다.")
    private Integer remainingPct;

    @NotNull(message = "source는 필수입니다.")
    private RegistrationSource source;
}
