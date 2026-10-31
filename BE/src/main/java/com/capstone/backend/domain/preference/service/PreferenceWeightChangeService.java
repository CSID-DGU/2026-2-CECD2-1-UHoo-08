package com.capstone.backend.domain.preference.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.preference.dto.response.PreferenceChangeRevertResponse;
import com.capstone.backend.domain.preference.repository.PreferenceWeightChangeRepository;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 가중치를 움직인 변경 한 건을 사용자가 되돌린다.
 *
 * BE 는 되돌린 시각만 남긴다. 가중치는 AI 가 되돌리지 않은 변경만 합쳐 다시 계산한다.
 */
@Service
@RequiredArgsConstructor
public class PreferenceWeightChangeService {

    private final PreferenceWeightChangeRepository changeRepository;
    private final RecommendationJobService recommendationJobService;

    /**
     * 내 변경이 아니면 NOT_FOUND, 이미 되돌렸으면 CHANGE_NOT_REVERTIBLE. 커밋되면 AI 에 가중치를 다시 계산하라고 알린다.
     * 되돌린 시각은 조건부로 남겨, 같은 변경을 동시에 되돌려도 한 요청만 성공한다.
     */
    @Transactional
    public PreferenceChangeRevertResponse revert(UUID userId, UUID changeId) {
        return revert(userId, changeId, OffsetDateTime.now());
    }

    PreferenceChangeRevertResponse revert(UUID userId, UUID changeId, OffsetDateTime now) {
        changeRepository.findByIdAndUserId(changeId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (changeRepository.markReverted(changeId, now) == 0) {
            throw new BusinessException(ErrorCode.CHANGE_NOT_REVERTIBLE);
        }

        recommendationJobService.requestFeedbackApply(userId);
        return new PreferenceChangeRevertResponse(changeId, true);
    }
}
