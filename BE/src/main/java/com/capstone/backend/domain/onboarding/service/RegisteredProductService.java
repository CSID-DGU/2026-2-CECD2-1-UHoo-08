package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.domain.onboarding.dto.RegisteredProductBatchRequest;

import java.util.UUID;

public interface RegisteredProductService {
    int saveBatch(UUID userId, RegisteredProductBatchRequest request);
}
