package com.capstone.backend.common.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 배치 실행 설정.
 *
 * 스케줄러 스레드 수와 이름은 application.yml 의 {@code spring.task.scheduling} 에 둔다.
 */
@Configuration
@EnableScheduling
@EnableConfigurationProperties(HwadamProperties.class)
public class SchedulingConfig {
}
