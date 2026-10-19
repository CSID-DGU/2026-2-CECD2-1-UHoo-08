package com.capstone.backend.domain.product.batch;

import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;

/**
 * 만료된 사진 인식 결과(photo_recognitions) 정리.
 *
 * 인식 결과는 등록까지 30분만 쓰고 끝나서, 지우지 않으면 계속 쌓인다.
 * 업로드한 사진은 등록된 제품의 근거가 될 수 있어 Storage 에서는 지우지 않고 행만 지운다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PhotoRecognitionCleanupScheduler {

    private final PhotoRecognitionRepository photoRecognitionRepository;

    @Scheduled(cron = "${hwadam.batch.photo-recognition-cleanup-cron}", zone = "${hwadam.batch.zone}")
    @Transactional
    public void deleteExpired() {
        int deleted = photoRecognitionRepository.deleteExpired(OffsetDateTime.now());
        log.info("[PhotoRecognitionCleanup] 만료된 사진 인식 결과 {}건 삭제", deleted);
    }
}
