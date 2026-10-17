package com.capstone.backend.common.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.scheduling.config.ScheduledTaskHolder;

import java.time.ZoneId;

import static org.assertj.core.api.Assertions.assertThat;

class SchedulingConfigTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
            .withUserConfiguration(SchedulingConfig.class);

    @Configuration
    static class SampleBatch {
        @Bean
        Sample sample() {
            return new Sample();
        }
    }

    static class Sample {
        @Scheduled(cron = "0 0 4 * * *", zone = "${hwadam.batch.zone}")
        void run() {
        }
    }

    @Test
    void Scheduled_메서드가_hwadam_시간대로_등록된다() {
        runner.withUserConfiguration(SampleBatch.class)
                .withPropertyValues("hwadam.batch.zone=Asia/Seoul")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    ScheduledTaskHolder holder = context.getBean(ScheduledTaskHolder.class);
                    assertThat(holder.getScheduledTasks()).hasSize(1);
                    assertThat(holder.getScheduledTasks().iterator().next().toString()).contains("Sample.run");
                });
    }

    @Test
    void 설정이_없으면_시간대_기본값은_서울이다() {
        runner.run(context ->
                assertThat(context.getBean(HwadamProperties.class).getBatch().getZone())
                        .isEqualTo(ZoneId.of("Asia/Seoul")));
    }

    @Test
    void 잘못된_시간대는_기동_단계에서_실패한다() {
        runner.withPropertyValues("hwadam.batch.zone=Mars/Base").run(context ->
                assertThat(context).hasFailed());
    }

    @Test
    void 스케줄러_스레드_수와_이름을_설정에서_받는다() {
        runner.withPropertyValues(
                        "spring.task.scheduling.pool.size=3",
                        "spring.task.scheduling.thread-name-prefix=hwadam-batch-")
                .run(context -> {
                    ThreadPoolTaskScheduler scheduler = context.getBean(ThreadPoolTaskScheduler.class);
                    assertThat(scheduler.getScheduledThreadPoolExecutor().getCorePoolSize()).isEqualTo(3);
                    assertThat(scheduler.getThreadNamePrefix()).isEqualTo("hwadam-batch-");
                });
    }
}
