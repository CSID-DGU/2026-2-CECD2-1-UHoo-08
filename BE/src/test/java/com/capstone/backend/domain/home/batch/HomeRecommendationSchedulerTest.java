package com.capstone.backend.domain.home.batch;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.HomeRunRequest;
import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.config.SchedulingConfig;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.scheduling.config.CronTask;
import org.springframework.scheduling.config.ScheduledTask;
import org.springframework.scheduling.config.ScheduledTaskHolder;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

class HomeRecommendationSchedulerTest {

    private final HomeRecommendationRepository repository = mock(HomeRecommendationRepository.class);
    private final AiInternalClient aiInternalClient = mock(AiInternalClient.class);
    private final HwadamProperties properties = new HwadamProperties();
    private final UUID first = UUID.randomUUID();
    private final UUID second = UUID.randomUUID();
    private final AtomicInteger waits = new AtomicInteger();

    /** 실제로 기다리지 않고 횟수만 센다 */
    private HomeRecommendationScheduler scheduler() {
        return new HomeRecommendationScheduler(repository, aiInternalClient, properties) {
            @Override
            boolean waitForNextCall() {
                waits.incrementAndGet();
                return true;
            }
        };
    }

    private void givenTargets(List<UUID> routine, List<UUID> env) {
        given(repository.findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, false)).willReturn(routine);
        given(repository.findCardTargets(HomeRecommendationKind.ENV, 1, true, false)).willReturn(env);
    }

    private HomeRunRequest run(UUID userId, String kind) {
        return new HomeRunRequest(userId.toString(), kind);
    }

    @Test
    void 루틴은_보유_2개_이상_환경은_지역과_보유_1개_이상을_고른_순서대로_요청한다() {
        givenTargets(List.of(first, second), List.of(second));

        scheduler().requestCards();

        InOrder order = inOrder(aiInternalClient);
        order.verify(aiInternalClient).runHome(run(first, "ROUTINE"));
        order.verify(aiInternalClient).runHome(run(second, "ROUTINE"));
        order.verify(aiInternalClient).runHome(run(second, "ENV"));
        order.verifyNoMoreInteractions();
    }

    @Test
    void 합성_사용자_포함은_설정을_따른다() {
        properties.getBatch().setHomeIncludeSynthetic(true);

        scheduler().requestCards();

        verify(repository).findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, true);
        verify(repository).findCardTargets(HomeRecommendationKind.ENV, 1, true, true);
    }

    @Test
    void 호출마다_기다린다() {
        givenTargets(List.of(first, second), List.of(second));

        scheduler().requestCards();

        assertThat(waits).hasValue(3);
    }

    @Test
    void 대상이_없으면_호출하지_않는다() {
        givenTargets(List.of(), List.of());

        scheduler().requestCards();

        verify(aiInternalClient, never()).runHome(any());
        assertThat(waits).hasValue(0);
    }

    @Test
    void 한_사용자가_실패해도_다음_사용자를_요청한다() {
        givenTargets(List.of(first, second), List.of());
        willThrow(new RuntimeException("connection refused")).given(aiInternalClient).runHome(run(first, "ROUTINE"));

        scheduler().requestCards();

        verify(aiInternalClient).runHome(run(second, "ROUTINE"));
    }

    @Test
    void 환경_대상_조회가_실패해도_루틴은_요청한다() {
        given(repository.findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, false)).willReturn(List.of(first));
        given(repository.findCardTargets(HomeRecommendationKind.ENV, 1, true, false))
                .willThrow(new RuntimeException("db down"));

        scheduler().requestCards();

        verify(aiInternalClient).runHome(run(first, "ROUTINE"));
    }

    @Test
    void 루틴_대상_조회가_실패해도_환경은_요청한다() {
        given(repository.findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, false))
                .willThrow(new RuntimeException("db down"));
        given(repository.findCardTargets(HomeRecommendationKind.ENV, 1, true, false)).willReturn(List.of(first));

        scheduler().requestCards();

        verify(aiInternalClient).runHome(run(first, "ENV"));
    }

    @Test
    void 기다리는_중_중단되면_남은_사용자와_다음_종류를_요청하지_않는다() {
        given(repository.findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, false))
                .willReturn(List.of(first, second));
        HomeRecommendationScheduler scheduler = new HomeRecommendationScheduler(repository, aiInternalClient, properties) {
            @Override
            boolean waitForNextCall() {
                return false;
            }
        };

        scheduler.requestCards();

        verify(aiInternalClient, times(1)).runHome(any());
        verify(repository, never()).findCardTargets(eq(HomeRecommendationKind.ENV), anyLong(), anyBoolean(), anyBoolean());
    }

    @Test
    void 호출_간격은_설정한_속도를_넘지_않도록_올림한다() {
        assertThat(HomeRecommendationScheduler.callGapMillis(2)).isEqualTo(500);
        assertThat(HomeRecommendationScheduler.callGapMillis(3)).isEqualTo(334);
        assertThat(HomeRecommendationScheduler.callGapMillis(600)).isEqualTo(2);
        assertThat(HomeRecommendationScheduler.callGapMillis(1000)).isEqualTo(1);
        assertThat(HomeRecommendationScheduler.callGapMillis(2000)).isEqualTo(1);
    }

    @Test
    void 중단_신호는_지우지_않고_남긴다() {
        properties.getBatch().setHomeCallsPerSecond(1);
        Thread.currentThread().interrupt();

        boolean waited = new HomeRecommendationScheduler(repository, aiInternalClient, properties).waitForNextCall();

        assertThat(waited).isFalse();
        assertThat(Thread.interrupted()).isTrue();
    }

    @Test
    void 기본_설정은_매일_6시_30분이고_초당_2회이며_합성_사용자를_빼고_cron은_설정으로_바꾼다() {
        assertThat(properties.getBatch().getHomeCron()).isEqualTo("0 30 6 * * *");
        assertThat(properties.getBatch().getHomeCallsPerSecond()).isEqualTo(2);
        assertThat(properties.getBatch().isHomeIncludeSynthetic()).isFalse();

        new ApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
                .withUserConfiguration(SchedulingConfig.class)
                .withBean(HomeRecommendationRepository.class, () -> repository)
                .withBean(AiInternalClient.class, () -> aiInternalClient)
                .withBean(HomeRecommendationScheduler.class)
                .withPropertyValues("hwadam.batch.home-cron=0 0 7 * * *", "hwadam.batch.zone=Asia/Seoul")
                .run(context -> assertThat(context.getBean(ScheduledTaskHolder.class).getScheduledTasks().stream()
                        .map(ScheduledTask::getTask)
                        .filter(CronTask.class::isInstance)
                        .map(task -> ((CronTask) task).getExpression())
                        .toList()).containsExactly("0 0 7 * * *"));
    }
}
