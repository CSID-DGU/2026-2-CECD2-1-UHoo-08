package com.capstone.backend.domain.recommendation.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

/** 세트 제품 교체. 칸과 교체 후보에서 고른 제품 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class BundleSwapRequest {

    @NotBlank(message = "slotKey는 필수입니다.")
    private String slotKey;

    @NotBlank(message = "productId는 필수입니다.")
    private String productId;
}
