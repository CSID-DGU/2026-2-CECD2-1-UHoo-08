package com.capstone.backend.domain.home.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Immutable;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * 지역별 하루 환경 집계(env_daily). 키는 (region, date) 다.
 *
 * AI 가 관측값을 모아 쓰고 BE 는 읽기만 한다. region 은 users.region 과 같은 시·도 이름이다.
 */
@Entity
@Immutable
@Table(name = "env_daily")
@IdClass(EnvDaily.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class EnvDaily {

    @Id
    @Column(name = "region", length = 50)
    private String region;

    @Id
    @Column(name = "date")
    private LocalDate date;

    @Column(name = "temp_avg")
    private Float tempAvg;

    @Column(name = "temp_min")
    private Float tempMin;

    @Column(name = "temp_max")
    private Float tempMax;

    @Column(name = "humidity_avg")
    private Float humidityAvg;

    @Column(name = "uv_max")
    private Float uvMax;

    @Column(name = "pm10_avg")
    private Float pm10Avg;

    @Column(name = "pm25_avg")
    private Float pm25Avg;

    /** 그날 집계에 쓴 관측 수. 0 이면 아예 못 받은 날이라, 4주 집계에서 "괜찮은 날"로 세면 안 된다 */
    @Column(name = "sample_count", nullable = false)
    private int sampleCount;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private String region;
        private LocalDate date;
    }
}
