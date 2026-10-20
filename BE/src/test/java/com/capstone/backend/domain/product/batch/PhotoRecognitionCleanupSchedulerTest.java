package com.capstone.backend.domain.product.batch;

import com.capstone.backend.common.config.SchedulingConfig;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.data.domain.Pageable;
import org.springframework.scheduling.config.CronTask;
import org.springframework.scheduling.config.ScheduledTask;
import org.springframework.scheduling.config.ScheduledTaskHolder;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class PhotoRecognitionCleanupSchedulerTest {

    private final PhotoRecognitionRepository repository = mock(PhotoRecognitionRepository.class);
    private final StorageService storageService = mock(StorageService.class);
    private final PhotoRecognitionCleanupScheduler scheduler =
            new PhotoRecognitionCleanupScheduler(repository, storageService);

    private static PhotoRecognition expired(String nameImageUrl, String dateImageUrl) {
        PhotoRecognition recognition = PhotoRecognition.builder()
                .userId(UUID.randomUUID())
                .nameImageUrl(nameImageUrl)
                .expiresAt(OffsetDateTime.now().minusMinutes(1))
                .build();
        ReflectionTestUtils.setField(recognition, "id", UUID.randomUUID());
        recognition.recordExpiry(dateImageUrl, null, null);
        return recognition;
    }

    @Test
    void 만료된_행의_사진을_먼저_지우고_그다음_행을_지운다() {
        PhotoRecognition both = expired("https://s/name1.jpg", "https://s/date1.jpg");
        PhotoRecognition nameOnly = expired("https://s/name2.jpg", null);
        given(repository.findByExpiresAtBeforeOrderByExpiresAtAsc(any(), any()))
                .willReturn(List.of(both, nameOnly), List.of());

        scheduler.deleteExpired();

        InOrder order = inOrder(storageService, repository);
        order.verify(storageService).delete("user-product-photos",
                List.of("https://s/name1.jpg", "https://s/date1.jpg", "https://s/name2.jpg"));
        order.verify(repository).deleteAllByIdInBatch(List.of(both.getId(), nameOnly.getId()));
    }

    @Test
    void 지금_시각보다_만료_시각이_이른_행을_묶음_크기만큼_읽는다() {
        given(repository.findByExpiresAtBeforeOrderByExpiresAtAsc(any(), any())).willReturn(List.of());

        scheduler.deleteExpired();

        ArgumentCaptor<OffsetDateTime> now = ArgumentCaptor.forClass(OffsetDateTime.class);
        ArgumentCaptor<Pageable> page = ArgumentCaptor.forClass(Pageable.class);
        verify(repository).findByExpiresAtBeforeOrderByExpiresAtAsc(now.capture(), page.capture());
        assertThat(now.getValue()).isCloseTo(OffsetDateTime.now(), within(5, ChronoUnit.SECONDS));
        assertThat(page.getValue().getPageSize()).isEqualTo(PhotoRecognitionCleanupScheduler.CHUNK_SIZE);
    }

    @Test
    void 만료된_행이_없으면_아무것도_지우지_않는다() {
        given(repository.findByExpiresAtBeforeOrderByExpiresAtAsc(any(), any())).willReturn(List.of());

        scheduler.deleteExpired();

        verifyNoInteractions(storageService);
        verify(repository, never()).deleteAllByIdInBatch(any());
    }

    @Test
    void 사진_삭제가_실패하면_행을_남기고_이번_실행을_멈춘다() {
        given(repository.findByExpiresAtBeforeOrderByExpiresAtAsc(any(), any()))
                .willReturn(List.of(expired("https://s/name1.jpg", null)));
        willThrow(new BusinessException(ErrorCode.INTERNAL_ERROR))
                .given(storageService).delete(any(), anyList());

        scheduler.deleteExpired();

        verify(repository, never()).deleteAllByIdInBatch(any());
        verify(storageService, times(1)).delete(any(), anyList());
    }

    @Test
    void 행이_지워지지_않아도_정해진_묶음_수에서_멈춘다() {
        given(repository.findByExpiresAtBeforeOrderByExpiresAtAsc(any(), any()))
                .willReturn(List.of(expired("https://s/name1.jpg", null)));

        scheduler.deleteExpired();

        verify(storageService, times(PhotoRecognitionCleanupScheduler.MAX_CHUNKS)).delete(any(), anyList());
    }

    @Test
    void 설정한_cron으로_배치가_등록된다() {
        new ApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
                .withUserConfiguration(SchedulingConfig.class)
                .withBean(PhotoRecognitionRepository.class, () -> mock(PhotoRecognitionRepository.class))
                .withBean(StorageService.class, () -> mock(StorageService.class))
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
