package com.capstone.backend.domain.product.batch;

import com.capstone.backend.common.config.SchedulingConfig;
import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.scheduling.config.CronTask;
import org.springframework.scheduling.config.ScheduledTask;
import org.springframework.scheduling.config.ScheduledTaskHolder;

import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class PhotoRecognitionCleanupSchedulerTest {

    @Test
    void 지금_시각보다_만료_시각이_이른_행을_지운다() {
        PhotoRecognitionRepository repository = mock(PhotoRecognitionRepository.class);
        given(repository.deleteExpired(any())).willReturn(2);

        new PhotoRecognitionCleanupScheduler(repository).deleteExpired();

        ArgumentCaptor<OffsetDateTime> now = ArgumentCaptor.forClass(OffsetDateTime.class);
        verify(repository).deleteExpired(now.capture());
        assertThat(now.getValue()).isCloseTo(OffsetDateTime.now(), within(5, ChronoUnit.SECONDS));
    }

    @Test
    void 설정한_cron으로_배치가_등록된다() {
        new ApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
                .withUserConfiguration(SchedulingConfig.class)
                .withBean(PhotoRecognitionRepository.class, () -> mock(PhotoRecognitionRepository.class))
                .withBean(PhotoRecognitionCleanupScheduler.class)
                .withPropertyValues(
                        "hwadam.batch.zone=Asia/Seoul",
                        "hwadam.batch.photo-recognition-cleanup-cron=0 0 * * * *")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    ScheduledTask task = context.getBean(ScheduledTaskHolder.class).getScheduledTasks().iterator().next();
                    assertThat(task.getTask()).isInstanceOf(CronTask.class);
                    assertThat(((CronTask) task.getTask()).getExpression()).isEqualTo("0 0 * * * *");
                    assertThat(task.toString()).contains("PhotoRecognitionCleanupScheduler.deleteExpired");
                });
    }
}
