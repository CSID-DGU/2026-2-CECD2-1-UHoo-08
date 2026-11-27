package com.capstone.backend.domain.preference.repository;

import com.capstone.backend.domain.preference.entity.PreferenceWeightChange;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

public interface PreferenceWeightChangeRepository extends JpaRepository<PreferenceWeightChange, UUID> {

    Optional<PreferenceWeightChange> findByIdAndUserId(UUID id, UUID userId);

    /** since 이후에 생긴 변경 중 되돌리지 않은 가장 최근 것 */
    Optional<PreferenceWeightChange> findFirstByUserIdAndRevertedAtIsNullAndCreatedAtAfterOrderByCreatedAtDesc(
            UUID userId, OffsetDateTime since);

    /**
     * 아직 되돌리지 않은 변경에 되돌린 시각을 남기고 바꾼 개수를 돌려준다.
     * 조건을 UPDATE 안에서 확인하므로, 같은 변경을 동시에 되돌려도 한 요청만 1을 받는다.
     */
    @Modifying(clearAutomatically = true)
    @Query("UPDATE PreferenceWeightChange c SET c.revertedAt = :now WHERE c.id = :id AND c.revertedAt IS NULL")
    int markReverted(@Param("id") UUID id, @Param("now") OffsetDateTime now);
}
