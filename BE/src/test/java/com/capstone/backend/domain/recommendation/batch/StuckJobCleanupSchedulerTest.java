package com.capstone.backend.domain.recommendation.batch;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.config.SchedulingConfig;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.scheduling.config.CronTask;
import org.springframework.scheduling.config.ScheduledTask;
import org.springframework.scheduling.config.ScheduledTaskHolder;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

class StuckJobCleanupSchedulerTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 22, 3, 0);

    private final RecommendationRepository repository = mock(RecommendationRepository.class);

    @Test
    void 대기_진행_중인_job은_15분_전보다_오래_갱신되지_않았으면_timeout으로_실패시킨다() {
        new StuckJobCleanupScheduler(repository, new HwadamProperties()).failStuckJobs(NOW);

        verify(repository).failStale(List.of(JobStatus.PENDING, JobStatus.IN_PROGRESS),
                LocalDateTime.of(2026, 10, 22, 2, 45), "timeout", NOW);
    }

    @Test
    void 되묻는_중인_job은_24시간이_지났을_때만_실패시킨다() {
        new StuckJobCleanupScheduler(repository, new HwadamProperties()).failStuckJobs(NOW);

        verify(repository).failStale(List.of(JobStatus.NEEDS_CLARIFICATION),
                LocalDateTime.of(2026, 10, 21, 3, 0), "clarification timeout", NOW);
    }

    @Test
    void 기준_시간은_설정에서_바꿀_수_있다() {
        HwadamProperties properties = new HwadamProperties();
        properties.getBatch().setStuckJobTimeout(Duration.ofMinutes(5));
        properties.getBatch().setClarificationTimeout(Duration.ofHours(1));

        new StuckJobCleanupScheduler(repository, properties).failStuckJobs(NOW);

        verify(repository).failStale(List.of(JobStatus.PENDING, JobStatus.IN_PROGRESS),
                NOW.minusMinutes(5), "timeout", NOW);
        verify(repository).failStale(List.of(JobStatus.NEEDS_CLARIFICATION),
                NOW.minusHours(1), "clarification timeout", NOW);
    }

    @Test
    void 완료와_실패된_job은_대상에_넣지_않는다() {
        new StuckJobCleanupScheduler(repository, new HwadamProperties()).failStuckJobs(NOW);

        verify(repository, never()).failStale(
                argThat(statuses -> statuses.contains(JobStatus.COMPLETED) || statuses.contains(JobStatus.FAILED)),
                any(), any(), any());
    }

    @Test
    void 설정한_cron과_기본_기준_시간으로_배치가_등록된다() {
        new ApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
                .withUserConfiguration(SchedulingConfig.class)
                .withBean(RecommendationRepository.class, () -> mock(RecommendationRepository.class))
                .withBean(StuckJobCleanupScheduler.class)
                .withPropertyValues(
                        "hwadam.batch.zone=Asia/Seoul",
                        "hwadam.batch.stuck-job-cleanup-cron=0 */10 * * * *")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    ScheduledTask task = context.getBean(ScheduledTaskHolder.class).getScheduledTasks().iterator().next();
                    assertThat(((CronTask) task.getTask()).getExpression()).isEqualTo("0 */10 * * * *");
                    assertThat(task.toString()).contains("StuckJobCleanupScheduler.failStuckJobs");

                    HwadamProperties.Batch batch = context.getBean(HwadamProperties.class).getBatch();
                    assertThat(batch.getStuckJobTimeout()).isEqualTo(Duration.ofMinutes(15));
                    assertThat(batch.getClarificationTimeout()).isEqualTo(Duration.ofHours(24));
                });
    }
}
