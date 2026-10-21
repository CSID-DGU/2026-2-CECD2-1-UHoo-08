package com.capstone.backend.common.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import java.time.ZoneId;

/**
 * application.yml 의 {@code hwadam.*} 설정 묶음.
 *
 * 환경 판정 기준값, 배치 cron 처럼 코드에 박으면 안 되는 값을 여기에 모은다. 각 값은 그 값을 쓰는 작업에서 추가한다.
 * 
 *   batch: 배치 공통(시간대). cron 은 멈춘 job 정리, 사진 인식 정리, 홈 배치에서 추가
 *   환경 판정 기준값은 홈, 환경에서 추가
 */
@Getter
@Setter
@Validated
@ConfigurationProperties(prefix = "hwadam")
public class HwadamProperties {

    @Valid
    private Batch batch = new Batch();

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
    }
}
