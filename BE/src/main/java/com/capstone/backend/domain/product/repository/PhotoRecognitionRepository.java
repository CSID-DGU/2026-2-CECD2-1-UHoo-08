package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.PhotoRecognition;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public interface PhotoRecognitionRepository extends JpaRepository<PhotoRecognition, UUID> {

    /** 만료된 인식 결과. 정리 배치가 사진을 지운 뒤 행을 지우려고 나눠 읽는다 */
    List<PhotoRecognition> findByExpiresAtBeforeOrderByExpiresAtAsc(OffsetDateTime now, Pageable pageable);
}
