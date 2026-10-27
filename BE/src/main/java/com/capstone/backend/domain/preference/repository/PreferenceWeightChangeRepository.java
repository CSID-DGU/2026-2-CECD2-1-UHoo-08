package com.capstone.backend.domain.preference.repository;

import com.capstone.backend.domain.preference.entity.PreferenceWeightChange;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

public interface PreferenceWeightChangeRepository extends JpaRepository<PreferenceWeightChange, UUID> {

    /** since 이후에 생긴 변경 중 되돌리지 않은 가장 최근 것 */
    Optional<PreferenceWeightChange> findFirstByUserIdAndRevertedAtIsNullAndCreatedAtAfterOrderByCreatedAtDesc(
            UUID userId, OffsetDateTime since);
}
