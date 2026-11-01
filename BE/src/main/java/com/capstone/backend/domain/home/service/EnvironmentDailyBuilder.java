package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties.EnvThresholds;
import com.capstone.backend.domain.home.dto.response.EnvironmentDailyResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentDailyResponse.Day;
import com.capstone.backend.domain.home.entity.EnvDaily;
import com.capstone.backend.domain.home.enums.EnvMetric;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.DoubleSummaryStatistics;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 환경 지표 하나의 날짜별 막대 그래프 데이터와 요약 문장.
 *
 * 기록이 없는 날도 날짜를 채워 값을 비워 둔다. 빠진 날이 그래프에 보여야 한다. 관측이 없는 날(sample_count=0)도 빈 날로 둔다.
 * 지표별 기준: 자외선은 기준 이상, 미세먼지(PM10)는 기준 초과, 습도는 기준 미만이면 넘은 날이고 기온은 기준이 없다.
 */
public final class EnvironmentDailyBuilder {

    static final String EMPTY_HEADLINE = "아직 기록이 없어요";
    static final String EMPTY_SUB_TEXT = "기록이 쌓이면 보여 드릴게요";
    /** 이 날 수를 볼 때는 기간을 "한 달"이라고 부른다 */
    static final int MONTH_DAYS = 28;

    private EnvironmentDailyBuilder() {
    }

    /** start ~ end(양끝 포함) 날짜를 모두 채운다 */
    public static EnvironmentDailyResponse build(EnvMetric metric, LocalDate start, LocalDate end,
                                                 List<EnvDaily> rows, EnvThresholds thresholds) {
        Map<LocalDate, EnvDaily> observed = rows.stream()
                .filter(row -> row.getSampleCount() > 0)
                .collect(Collectors.toMap(EnvDaily::getDate, Function.identity(), (a, b) -> a));
        Float threshold = threshold(metric, thresholds);

        List<Day> days = new ArrayList<>();
        for (LocalDate date = start; !date.isAfter(end); date = date.plusDays(1)) {
            EnvDaily row = observed.get(date);
            Float value = row == null ? null : valueOf(metric, row);
            days.add(new Day(date, value, exceeded(metric, value, threshold)));
        }

        int dayCount = days.size();
        List<Float> values = days.stream().map(Day::getValue).filter(Objects::nonNull).toList();
        if (values.isEmpty()) {
            return new EnvironmentDailyResponse(metric, metric.label(), EMPTY_HEADLINE, EMPTY_SUB_TEXT, threshold, days);
        }
        int exceededCount = (int) days.stream().filter(Day::isExceeded).count();
        int percent = (int) Math.round(exceededCount * 100.0 / values.size());
        String period = dayCount == MONTH_DAYS ? "한 달" : "최근 " + dayCount + "일";

        String headline;
        String subText;
        switch (metric) {
            case UV -> {
                headline = number(threshold) + " 이상인 날이 " + exceededCount + "일";
                subText = "'높음' 구간이 " + period + "의 " + percent + "%예요";
            }
            case PM -> {
                headline = "미세먼지 나쁨인 날이 " + exceededCount + "일";
                subText = "'나쁨' 구간이 " + period + "의 " + percent + "%예요";
            }
            case HUMIDITY -> {
                headline = number(threshold) + "% 미만인 날이 " + exceededCount + "일";
                subText = "'건조' 구간이 " + period + "의 " + percent + "%예요";
            }
            default -> {
                DoubleSummaryStatistics temps = values.stream().mapToDouble(Float::doubleValue).summaryStatistics();
                headline = "평균 기온 " + Math.round(temps.getAverage()) + "°C";
                subText = "가장 낮은 날 " + Math.round(temps.getMin()) + "°C, 가장 높은 날 " + Math.round(temps.getMax()) + "°C";
            }
        }
        return new EnvironmentDailyResponse(metric, metric.label(), headline, subText, threshold, days);
    }

    static Float threshold(EnvMetric metric, EnvThresholds thresholds) {
        return switch (metric) {
            case UV -> thresholds.getUvHigh();
            case PM -> thresholds.getPm10Bad();
            case HUMIDITY -> thresholds.getHumidityLow();
            case TEMP -> null;
        };
    }

    static Float valueOf(EnvMetric metric, EnvDaily row) {
        return switch (metric) {
            case UV -> row.getUvMax();
            case PM -> row.getPm10Avg();
            case HUMIDITY -> row.getHumidityAvg();
            case TEMP -> row.getTempAvg();
        };
    }

    static boolean exceeded(EnvMetric metric, Float value, Float threshold) {
        if (value == null || threshold == null) {
            return false;
        }
        return switch (metric) {
            case UV -> value >= threshold;
            case PM -> value > threshold;
            case HUMIDITY -> value < threshold;
            case TEMP -> false;
        };
    }

    /** 6.0 → "6", 6.5 → "6.5" */
    private static String number(Float value) {
        return value % 1 == 0 ? String.valueOf(value.intValue()) : String.valueOf(value);
    }
}
