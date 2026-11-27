package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.domain.onboarding.dto.FrequentlyUsedProductBatchRequest;

import java.util.UUID;

public interface FrequentlyUsedProductService {
    int saveBatch(UUID userId, FrequentlyUsedProductBatchRequest request);
}
