package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse.Preset;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** 추천 결과에 조건을 더해 다시 찾는 조건 수정 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationRefineService {

    /** 자주 고른 조건을 셀 기간 */
    static final Duration FREQUENT_WINDOW = Duration.ofDays(30);

    private final RecommendationRepository recommendationRepository;
    private final JsonUtil jsonUtil;

    /**
     * 조건 추가 선택지. 지금 조건은 결과 상단의 조건 칩과 같은 값이고, 결과가 아직 없으면 비어 있다.
     * 자주 고른 조건은 지금 보는 job 과 상관없이 이 사용자가 최근 30일 동안 두 번 이상 고른 조건이다.
     */
    @Transactional(readOnly = true)
    public RefinementOptionsResponse getOptions(UUID userId, UUID jobId) {
        return getOptions(userId, jobId, LocalDateTime.now());
    }

    RefinementOptionsResponse getOptions(UUID userId, UUID jobId, LocalDateTime now) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        Set<RefinePreset> frequent = RefinePresetCounter.frequent(
                recommendationRepository.findRefinePresetsSince(userId, now.minus(FREQUENT_WINDOW)));
        List<Preset> presets = Arrays.stream(RefinePreset.values())
                .map(preset -> new Preset(preset, preset.label(), frequent.contains(preset)))
                .toList();
        return new RefinementOptionsResponse(currentConditions(job), presets);
    }

    /** 결과의 질의 요약으로 만든 조건 칩. 상품 기준 추천(v1) job 이거나 결과가 없거나 읽을 수 없으면 빈 목록 */
    private List<String> currentConditions(Recommendation job) {
        if (job.getBasis() == null || job.getResult() == null) {
            return List.of();
        }
        try {
            return SummaryBuilder.conditions(jsonUtil.readTree(job.getResult()).path("query"));
        } catch (BusinessException e) {
            log.warn("[RecommendationRefine] job 의 결과를 읽지 못해 지금 조건을 비워 둔다: jobId={}", job.getId());
            return List.of();
        }
    }
}
