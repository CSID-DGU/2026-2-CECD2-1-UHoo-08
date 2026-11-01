package com.capstone.backend.domain.home.repository;

import java.util.UUID;

/** 기간 동안 제품 하나의 트렌드 지수 합 */
public record TrendScoreSum(UUID productId, Double total) {
}
