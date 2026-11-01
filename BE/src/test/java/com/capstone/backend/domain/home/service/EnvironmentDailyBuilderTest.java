package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties.EnvThresholds;
import com.capstone.backend.domain.home.dto.response.EnvironmentDailyResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentDailyResponse.Day;
import com.capstone.backend.domain.home.entity.EnvDaily;
import com.capstone.backend.domain.home.enums.EnvMetric;
import org.junit.jupiter.api.Test;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class EnvironmentDailyBuilderTest {

    private static final LocalDate END = LocalDate.of(2026, 9, 16);
    private static final EnvThresholds THRESHOLDS = new EnvThresholds();

    /** AI 가 쓰는 읽기 전용 엔티티라 생성자가 없다. 저장된 행을 읽어 온 것처럼 값을 채운다 */
    private static EnvDaily day(LocalDate date, int sampleCount, Float temp, Float humidity, Float uv, Float pm10) {
        EnvDaily day = BeanUtils.instantiateClass(EnvDaily.class);
        ReflectionTestUtils.setField(day, "region", "경기");
        ReflectionTestUtils.setField(day, "date", date);
        ReflectionTestUtils.setField(day, "sampleCount", sampleCount);
        ReflectionTestUtils.setField(day, "tempAvg", temp);
        ReflectionTestUtils.setField(day, "humidityAvg", humidity);
        ReflectionTestUtils.setField(day, "uvMax", uv);
        ReflectionTestUtils.setField(day, "pm10Avg", pm10);
        return day;
    }

    @Test
    void 기록이_없거나_관측이_없는_날도_날짜를_채워_값을_비운다() {
        LocalDate start = END.minusDays(3);
        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.UV, start, END, List.of(
                day(END, 24, null, null, 7.2f, null),
                day(END.minusDays(2), 0, null, null, 9f, null),   // 관측이 없는 날
                day(start, 24, null, null, 4.1f, null)), THRESHOLDS);

        assertThat(response.getDays())
                .extracting(Day::getDate, Day::getValue, Day::isExceeded)
                .containsExactly(
                        tuple(start, 4.1f, false),
                        tuple(END.minusDays(2), null, false),
                        tuple(END.minusDays(1), null, false),
                        tuple(END, 7.2f, true));
        assertThat(response.getLabel()).isEqualTo("자외선 지수");
        assertThat(response.getThreshold()).isEqualTo(6f);
        assertThat(response.getHeadline()).isEqualTo("6 이상인 날이 1일");
        assertThat(response.getSubText()).isEqualTo("'높음' 구간이 최근 4일의 50%예요");
    }

    @Test
    void 자외선은_기준과_같아도_넘은_날이고_28일이면_한_달이라고_부른다() {
        LocalDate start = END.minusDays(27);
        List<EnvDaily> rows = new ArrayList<>();
        for (int i = 0; i < 28; i++) {
            rows.add(day(start.plusDays(i), 24, null, null, i < 22 ? 6f : 5.9f, null));
        }

        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.UV, start, END, rows, THRESHOLDS);

        assertThat(response.getHeadline()).isEqualTo("6 이상인 날이 22일");
        assertThat(response.getSubText()).isEqualTo("'높음' 구간이 한 달의 79%예요");
    }

    @Test
    void 미세먼지는_기준을_넘어야_나쁜_날이다() {
        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.PM, END.minusDays(1), END, List.of(
                day(END.minusDays(1), 24, null, null, null, 80f),
                day(END, 24, null, null, null, 81f)), THRESHOLDS);

        assertThat(response.getDays()).extracting(Day::isExceeded).containsExactly(false, true);
        assertThat(response.getLabel()).isEqualTo("미세먼지");
        assertThat(response.getHeadline()).isEqualTo("미세먼지 나쁨인 날이 1일");
        assertThat(response.getSubText()).isEqualTo("'나쁨' 구간이 최근 2일의 50%예요");
    }

    @Test
    void 습도는_기준보다_낮으면_건조한_날이다() {
        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.HUMIDITY, END.minusDays(1), END, List.of(
                day(END.minusDays(1), 24, null, 40f, null, null),
                day(END, 24, null, 39.5f, null, null)), THRESHOLDS);

        assertThat(response.getDays()).extracting(Day::isExceeded).containsExactly(false, true);
        assertThat(response.getThreshold()).isEqualTo(40f);
        assertThat(response.getHeadline()).isEqualTo("40% 미만인 날이 1일");
        assertThat(response.getSubText()).isEqualTo("'건조' 구간이 최근 2일의 50%예요");
    }

    @Test
    void 기온은_기준선이_없고_평균과_최저_최고를_보여_준다() {
        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.TEMP, END.minusDays(2), END, List.of(
                day(END.minusDays(2), 24, 18.2f, null, null, null),
                day(END.minusDays(1), 24, 24.6f, null, null, null),
                day(END, 24, 29.4f, null, null, null)), THRESHOLDS);

        assertThat(response.getThreshold()).isNull();
        assertThat(response.getDays()).noneMatch(Day::isExceeded);
        assertThat(response.getHeadline()).isEqualTo("평균 기온 24°C");
        assertThat(response.getSubText()).isEqualTo("가장 낮은 날 18°C, 가장 높은 날 29°C");
    }

    @Test
    void 기록이_하나도_없으면_빈_날짜와_안내_문구다() {
        EnvironmentDailyResponse response = EnvironmentDailyBuilder.build(EnvMetric.UV, END.minusDays(6), END, List.of(),
                THRESHOLDS);

        assertThat(response.getDays()).hasSize(7).allMatch(day -> day.getValue() == null && !day.isExceeded());
        assertThat(response.getHeadline()).isEqualTo("아직 기록이 없어요");
        assertThat(response.getSubText()).isEqualTo("기록이 쌓이면 보여 드릴게요");
    }
}
