package com.capstone.backend.domain.recommendation.repository;

import com.capstone.backend.domain.recommendation.entity.SearchLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

public interface SearchLogRepository extends JpaRepository<SearchLog, Long> {

    /** 이 job 의 검색 기록. 자연어 추천 요청 한 번에 한 줄이다 */
    List<SearchLog> findByJobId(UUID jobId);

    /**
     * 아직 답을 받지 않은 이 job 의 검색 기록을 답 받음으로 바꾸고 바꾼 개수를 돌려준다.
     * 조건을 UPDATE 안에서 확인하므로, 같은 job 에 답이 동시에 와도 한 요청만 1을 받는다.
     */
    @Modifying(clearAutomatically = true)
    @Query("UPDATE SearchLog s SET s.clarified = true WHERE s.jobId = :jobId AND s.clarified = false")
    int markClarified(@Param("jobId") UUID jobId);

    /** 답을 AI 에 넘기지 못했을 때 답 받음 표시를 되돌린다. 트랜잭션이 끝난 뒤 부르므로 자기 트랜잭션에서 돈다 */
    @Transactional
    @Modifying(clearAutomatically = true)
    @Query("UPDATE SearchLog s SET s.clarified = false WHERE s.jobId = :jobId")
    int unmarkClarified(@Param("jobId") UUID jobId);
}
