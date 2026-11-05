package com.capstone.backend.domain.onboarding.repository;

import com.capstone.backend.domain.onboarding.entity.Registered;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface RegisteredRepository extends JpaRepository<Registered, UUID> {
    List<Registered> findByUserId(UUID userId);
    boolean existsByUserIdAndProductId(UUID userId, UUID productId);
    long countByUserId(UUID userId);
}
