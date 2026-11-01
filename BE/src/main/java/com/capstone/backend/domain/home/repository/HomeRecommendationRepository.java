package com.capstone.backend.domain.home.repository;

import com.capstone.backend.domain.home.entity.HomeRecommendation;
import org.springframework.data.jpa.repository.JpaRepository;

public interface HomeRecommendationRepository extends JpaRepository<HomeRecommendation, HomeRecommendation.Key> {
}
