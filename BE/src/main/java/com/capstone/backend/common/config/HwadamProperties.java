package com.capstone.backend.common.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.Duration;
import java.time.ZoneId;

/**
 * application.yml 의 {@code hwadam.*} 설정 묶음.
 *
 * 환경 판정 기준값, 배치 cron 처럼 코드에 박으면 안 되는 값을 여기에 모은다. 각 값은 그 값을 쓰는 작업에서 추가한다.
 * 
 *   zone: 서비스가 "오늘"을 정하는 시간대. 배치 cron 시간대와 따로 둔다
 *   batch: 배치 공통(시간대). cron 은 멈춘 job 정리, 사진 인식 정리, 홈 배치에서 추가
 *   env: 환경 판정 기준값. 환경 요약, 일별 추이에서 쓴다
 */
@Getter
@Setter
@Validated
@ConfigurationProperties(prefix = "hwadam")
public class HwadamProperties {

    /**
     * 서비스가 "오늘"을 정하는 시간대. 화면의 날짜와 하루 환경 집계(env_daily.date)는 한국 날짜 기준이다.
     * 서버(컨테이너)는 UTC 로 돌기 때문에 LocalDate.now() 를 그대로 쓰면 한국 시간 오전 9시 전에는 전날이 된다.
     */
    @NotNull
    private ZoneId zone = ZoneId.of("Asia/Seoul");

    @Valid
    private Batch batch = new Batch();

    @Valid
    private EnvThresholds env = new EnvThresholds();

    @Getter
    @Setter
    public static class Batch {

        /**
         * cron 을 해석할 시간대. 서버(컨테이너)는 UTC 로 돌기 때문에 "매일 새벽 4시" 같은 cron 은 이 시간대 기준으로 맞춘다.
         * {@code @Scheduled(cron = "${hwadam.batch.xxx-cron}", zone = "${hwadam.batch.zone}")} 처럼 쓴다.
         */
        @NotNull
        private ZoneId zone = ZoneId.of("Asia/Seoul");

        /** 만료된 사진 인식 결과 정리. 기본 매시 정각 */
        @NotBlank
        private String photoRecognitionCleanupCron = "0 0 * * * *";

        /** 멈춘 추천 job 정리. 기본 10분마다 */
        @NotBlank
        private String stuckJobCleanupCron = "0 */10 * * * *";

        /** 대기·진행 중인 job 이 이만큼 갱신되지 않으면 멈춘 것으로 본다 */
        @NotNull
        private Duration stuckJobTimeout = Duration.ofMinutes(15);

        /** 되묻는 중인 job 이 이만큼 답을 받지 못하면 실패로 둔다. 사용자를 기다리는 정상 상태라 길게 둔다 */
        @NotNull
        private Duration clarificationTimeout = Duration.ofHours(24);

        /** 홈 카드 생성 요청. 기본 매일 06:30 */
        @NotBlank
        private String homeCron = "0 30 6 * * *";

        /** 홈 카드 생성을 AI 에 요청하는 초당 횟수 */
        @Positive
        private int homeCallsPerSecond = 2;

        /** 합성 사용자의 홈 카드도 만들지. 실제 사용자가 아니라 AI 비용만 들어 기본은 만들지 않는다 */
        private boolean homeIncludeSynthetic = false;
    }

    /** 하루 환경 집계를 "나쁜 날"로 볼 기준값 */
    @Getter
    @Setter
    public static class EnvThresholds {

        /** 최고 자외선 지수가 이 값 이상이면 자외선 높은 날 */
        @NotNull
        private Float uvHigh = 6f;

        /** PM10 평균(㎍/㎥)이 이 값을 넘으면 미세먼지 나쁜 날 */
        @NotNull
        private Float pm10Bad = 80f;

        /** PM2.5 평균(㎍/㎥)이 이 값을 넘으면 미세먼지 나쁜 날 */
        @NotNull
        private Float pm25Bad = 35f;

        /** 습도 평균(%)이 이 값보다 낮으면 건조한 날 */
        @NotNull
        private Float humidityLow = 40f;

        /** 최근 7일 평균 습도가 3주 전 7일 평균과 이만큼(%p) 이상 다르면 계절이 바뀌는 것으로 본다 */
        @NotNull
        private Float humidityChange = 15f;
    }
}
