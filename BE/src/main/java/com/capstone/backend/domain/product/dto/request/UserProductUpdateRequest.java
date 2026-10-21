package com.capstone.backend.domain.product.dto.request;

import com.capstone.backend.domain.product.enums.UserProductStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

/**
 * 보유 제품 수정. 보낸 필드만 바꾸고, null 이거나 보내지 않은 필드는 그대로 둔다.
 * 보관 위치는 쓰지 않는 기능이라 받지 않는다(보내도 무시한다).
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserProductUpdateRequest {

    @Min(value = 0, message = "remainingPct는 0~100이어야 합니다.")
    @Max(value = 100, message = "remainingPct는 0~100이어야 합니다.")
    private Integer remainingPct;

    /** USING, FINISHED, DISCARDED */
    private UserProductStatus status;

    /** 다 쓴 날. 다 쓴 제품에만 의미가 있어 결과 상태가 FINISHED 일 때만 반영한다 */
    private LocalDate finishedAt;

    private LocalDate openedAt;

    private LocalDate expiryDate;

    @Min(value = 1, message = "paoMonths는 1 이상이어야 합니다.")
    private Integer paoMonths;
}
