package com.capstone.backend.domain.recommendation.repository;

import com.capstone.backend.domain.recommendation.entity.SearchLog;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SearchLogRepository extends JpaRepository<SearchLog, Long> {
}
