package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.PhotoRecognition;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.UUID;

public interface PhotoRecognitionRepository extends JpaRepository<PhotoRecognition, UUID> {

    /** 만료된 인식 결과를 한 문장으로 지우고 지운 행 수를 돌려준다 */
    @Modifying
    @Query("DELETE FROM PhotoRecognition p WHERE p.expiresAt < :now")
    int deleteExpired(@Param("now") OffsetDateTime now);
}
