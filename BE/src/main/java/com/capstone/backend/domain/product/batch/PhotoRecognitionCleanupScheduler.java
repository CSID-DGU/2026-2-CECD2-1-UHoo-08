package com.capstone.backend.domain.product.batch;

import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import com.capstone.backend.domain.product.service.PhotoRecognitionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Stream;

/**
 * 만료된 사진 인식 결과(photo_recognitions)와 그 사진 정리.
 *
 * 인식 결과는 등록까지 30분만 쓰고 끝나서, 지우지 않으면 계속 쌓인다.
 * 업로드한 사진도 등록 흐름에서만 쓰고 다른 곳에서 가리키지 않으므로 함께 지운다.
 * 사진을 먼저 지우고 행을 지운다. 행부터 지우면 사진을 가리키는 기록이 사라져 다시 지울 수 없다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PhotoRecognitionCleanupScheduler {

    /** Storage 삭제 한 번에 보내는 행 수. 한 행에 사진이 최대 두 장이다 */
    static final int CHUNK_SIZE = 100;
    /** 한 번 실행에서 처리하는 최대 묶음 수. 삭제가 반영되지 않아도 무한히 돌지 않게 한다 */
    static final int MAX_CHUNKS = 50;

    private final PhotoRecognitionRepository photoRecognitionRepository;
    private final StorageService storageService;

    @Scheduled(cron = "${hwadam.batch.photo-recognition-cleanup-cron}", zone = "${hwadam.batch.zone}")
    public void deleteExpired() {
        OffsetDateTime now = OffsetDateTime.now();
        int deleted = 0;

        for (int i = 0; i < MAX_CHUNKS; i++) {
            List<PhotoRecognition> expired = photoRecognitionRepository
                    .findByExpiresAtBeforeOrderByExpiresAtAsc(now, PageRequest.of(0, CHUNK_SIZE));
            if (expired.isEmpty()) {
                break;
            }

            List<String> imageUrls = expired.stream()
                    .flatMap(r -> Stream.of(r.getNameImageUrl(), r.getDateImageUrl()))
                    .filter(Objects::nonNull)
                    .toList();
            try {
                storageService.delete(PhotoRecognitionService.BUCKET, imageUrls);
            } catch (RuntimeException e) {
                // 행을 남겨 두면 다음 실행에서 같은 사진을 다시 지운다
                log.error("[PhotoRecognitionCleanup] 사진 삭제 실패로 행을 남기고 다음 실행에서 다시 시도: {}건", expired.size());
                break;
            }

            List<UUID> ids = expired.stream().map(PhotoRecognition::getId).toList();
            photoRecognitionRepository.deleteAllByIdInBatch(ids);
            deleted += ids.size();
        }

        log.info("[PhotoRecognitionCleanup] 만료된 사진 인식 결과 {}건과 그 사진 삭제", deleted);
    }
}
