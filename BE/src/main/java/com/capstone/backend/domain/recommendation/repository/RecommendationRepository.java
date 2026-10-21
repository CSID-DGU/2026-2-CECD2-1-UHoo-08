package com.capstone.backend.domain.recommendation.repository;

import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Optional;
import java.util.UUID;

public interface RecommendationRepository extends JpaRepository<Recommendation, UUID> {

    @Query("SELECT r FROM Recommendation r WHERE r.id = :id AND r.user.id = :userId")
    Optional<Recommendation> findByIdAndUserId(@Param("id") UUID id, @Param("userId") UUID userId);

    /**
     * 주어진 상태이면서 cutoff 전에 마지막으로 갱신된 job 을 한 문장으로 실패로 바꾸고 바꾼 개수를 돌려준다.
     * 조건을 UPDATE 안에서 확인하므로, 그사이 AI 가 갱신한 job 은 바뀌지 않는다.
     */
    @Modifying(clearAutomatically = true)
    @Query("UPDATE Recommendation r SET r.status = com.capstone.backend.domain.recommendation.enums.JobStatus.FAILED, "
            + "r.errorMsg = :errorMsg, r.updatedAt = :now "
            + "WHERE r.status IN :statuses AND r.updatedAt < :cutoff")
    int failStale(@Param("statuses") Collection<JobStatus> statuses, @Param("cutoff") LocalDateTime cutoff,
                  @Param("errorMsg") String errorMsg, @Param("now") LocalDateTime now);
}
