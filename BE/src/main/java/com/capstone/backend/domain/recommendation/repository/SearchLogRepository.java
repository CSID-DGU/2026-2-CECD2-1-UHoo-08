package com.capstone.backend.domain.recommendation.repository;

import com.capstone.backend.domain.recommendation.entity.SearchLog;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface SearchLogRepository extends JpaRepository<SearchLog, Long> {

    /** 이 job 의 검색 기록. 자연어 추천 요청 한 번에 한 줄이다 */
    List<SearchLog> findByJobId(UUID jobId);
}
