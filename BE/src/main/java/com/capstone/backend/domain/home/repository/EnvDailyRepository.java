package com.capstone.backend.domain.home.repository;

import com.capstone.backend.domain.home.entity.EnvDaily;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface EnvDailyRepository extends JpaRepository<EnvDaily, EnvDaily.Key> {

    /** 지역의 from ~ to(양끝 포함) 하루 환경 집계 */
    List<EnvDaily> findByRegionAndDateBetween(String region, LocalDate from, LocalDate to);
}
