package com.capstone.backend.domain.onboarding.dto;

import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

@Getter
@NoArgsConstructor
public class FrequentlyUsedProductBatchRequest {

    /** 한 번에 보낼 수 있는 제품 수 */
    public static final int MAX_PRODUCTS = 50;

    @Size(max = MAX_PRODUCTS, message = "productIds는 50개 이하여야 합니다.")
    private List<UUID> productIds;
}
