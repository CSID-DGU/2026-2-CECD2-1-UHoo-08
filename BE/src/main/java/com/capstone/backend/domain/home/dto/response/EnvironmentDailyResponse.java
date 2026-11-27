package com.capstone.backend.domain.home.dto.response;

import com.capstone.backend.domain.home.enums.EnvMetric;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;

/** 환경 지표 하나의 날짜별 값. 요즘 지내는 환경 화면의 막대 그래프 데이터다 */
@Getter
@AllArgsConstructor
public class EnvironmentDailyResponse {
    private EnvMetric metric;
    /** 지표 이름. 예: 자외선 지수 */
    private String label;
    /** 예: 6 이상인 날이 22일 */
    private String headline;
    /** 예: '높음' 구간이 한 달의 79%예요 */
    private String subText;
    /** 점선 기준선. 기준이 없는 지표(기온)는 null */
    private Float threshold;
    /** 오래된 순. 기록이 없는 날도 들어 있다 */
    private List<Day> days;

    @Getter
    @AllArgsConstructor
    public static class Day {
        private LocalDate date;
        /** 그날 값. 기록이 없거나 관측이 없는 날은 null */
        private Float value;
        /** 기준을 넘었는지. 값이 없거나 기준이 없는 지표면 false */
        private boolean exceeded;
    }
}
