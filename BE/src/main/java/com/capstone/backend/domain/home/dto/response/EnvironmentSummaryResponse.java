package com.capstone.backend.domain.home.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

/** 최근 4주 누적 환경과, 그 환경이 요구하는 제품 조건을 지금 루틴이 채우는지 */
@Getter
@AllArgsConstructor
public class EnvironmentSummaryResponse {
    /** 화면 표시용 지역 이름. 예: 고양시 덕양구 */
    private String regionName;
    private LocalDate periodStart;
    private LocalDate periodEnd;
    /** 기간 중 관측이 있는 날 수 */
    private int dayCount;
    private Stats stats;
    /** 계절이 바뀌는 중이 아니면 null */
    private SeasonChange seasonChange;
    private List<Condition> conditions;
    /** 보유 제품이 채우지 못한 조건 수 */
    private int missingCount;
    /** 기간 중 환경 기록이 마지막으로 갱신된 시각. 기록이 없으면 null */
    private OffsetDateTime updatedAt;

    @Getter
    @AllArgsConstructor
    public static class Stats {
        /** 자외선 높은 날 수 */
        private int uvHighDays;
        /** 미세먼지 나쁜 날 수 */
        private int dustBadDays;
        /** 평균 습도(%). 습도 기록이 없으면 null */
        private Integer avgHumidity;
    }

    @Getter
    @AllArgsConstructor
    public static class SeasonChange {
        private String title;
        private String message;
    }

    @Getter
    @AllArgsConstructor
    public static class Condition {
        /** UV_PROTECT, SOOTHING, BARRIER */
        private String key;
        private String label;
        /** 이 조건이 필요한 이유. 예: 미세먼지 14일 */
        private String basis;
        /** 보유 제품이 채우는지 */
        private boolean covered;
        /** 채우는 보유 제품. 채우지 못하면 null */
        private String coveredBy;
    }
}
