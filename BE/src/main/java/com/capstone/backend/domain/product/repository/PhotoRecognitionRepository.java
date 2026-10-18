package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.PhotoRecognition;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface PhotoRecognitionRepository extends JpaRepository<PhotoRecognition, UUID> {
}
