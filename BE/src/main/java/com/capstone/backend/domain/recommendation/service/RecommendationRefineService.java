package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.request.RefinementRequest;
import com.capstone.backend.domain.recommendation.dto.response.RefinementHistoryResponse;
import com.capstone.backend.domain.recommendation.dto.response.RefinementHistoryResponse.Step;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.RefinementOptionsResponse.Preset;
import com.capstone.backend.domain.recommendation.dto.response.RefinementResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService.NewJob;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 추천 결과에 조건을 더해 다시 찾는 조건 수정(재탐색).
 *
 * 직전 결과를 거르는 것이 아니라, 새 job 으로 AI 추천 실행을 다시 부르고 직전 job 을 알려 준다.
 * AI 가 직전 상태에서 조건을 이어받아 더한 조건으로 후보를 다시 찾으므로 후보 수는 유지된다.
 * 조건 추가 선택지와 지금까지의 조건 수정 이력도 여기서 만든다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationRefineService {

    /** 자주 고른 조건을 셀 기간 */
    static final Duration FREQUENT_WINDOW = Duration.ofDays(30);
    /** 조건 수정은 직전 상태를 이어받아 처음 검색보다 빠르다 */
    static final int REFINE_ESTIMATED_SECONDS = 4;
    static final String FIRST_STEP_LABEL = "처음 검색";
    /** 이력에 담는 최대 단계 수. 직전 job 이 잘못 이어져 있어도 끝없이 올라가지 않게 한다 */
    static final int MAX_HISTORY_STEPS = 50;

    private final RecommendationRepository recommendationRepository;
    private final JsonUtil jsonUtil;
    private final RecommendationJobService recommendationJobService;

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

    /**
     * 직전 job 에 조건을 더해 새 job 을 만든다. 추천 기준과 쓰실 분 정보는 직전 job 에서 가져온다.
     * 직전 job 이 끝나지 않았으면 JOB_NOT_COMPLETED, 상품 기준 추천(v1) job 이면 이어 갈 상태가 없어 VALIDATION_ERROR.
     * 저장 뒤 AI 에 가중치 반영도 알린다. 조건 수정 패턴을 가중치에 반영하는 일은 AI 가 한다.
     */
    @Transactional
    public RefinementResponse refine(UUID userId, UUID parentJobId, RefinementRequest request) {
        Recommendation parent = recommendationRepository.findByIdAndUserId(parentJobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (parent.getBasis() == null) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        if (parent.getStatus() != JobStatus.COMPLETED) {
            throw new BusinessException(ErrorCode.JOB_NOT_COMPLETED);
        }

        List<RefinePreset> presets = presetsOf(request);
        String freeText = request.getFreeText() == null || request.getFreeText().isBlank()
                ? null : request.getFreeText().strip();
        if (presets.isEmpty() && freeText == null) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }

        Recommendation job = recommendationJobService.startJob(new NewJob(
                parent.getUser(), rawQuery(presets, freeText), parent.getBasis(), parent.getTargetProfile(),
                parent.getId(),
                presets.isEmpty() ? null : presets.stream().map(RefinePreset::name).toArray(String[]::new),
                freeText));
        recommendationJobService.requestFeedbackApply(userId);
        return new RefinementResponse(job.getId(), parent.getId(), REFINE_ESTIMATED_SECONDS);
    }

    /** 고른 조건. 겹친 키는 하나로 줄이고 선택지 순서로 둔다 */
    static List<RefinePreset> presetsOf(RefinementRequest request) {
        if (request.getPresetKeys() == null) {
            return List.of();
        }
        EnumSet<RefinePreset> presets = EnumSet.noneOf(RefinePreset.class);
        request.getPresetKeys().stream().filter(Objects::nonNull).forEach(presets::add);
        return new ArrayList<>(presets);
    }

    /** AI 에 보낼 문장. 고른 조건의 문장 뒤에 직접 쓴 조건을 붙여 쉼표로 잇는다 */
    static String rawQuery(List<RefinePreset> presets, String freeText) {
        List<String> parts = new ArrayList<>(presets.stream().map(RefinePreset::sentence).toList());
        if (freeText != null) {
            parts.add(freeText);
        }
        return String.join(", ", parts);
    }

    /**
     * 조건 수정 이력. 받은 job 에서 직전 job 을 따라 처음 검색까지 올라간 뒤 처음 → 지금 순서로 나열한다.
     * 한 줄 경로만 보여 주고, 같은 단계에서 갈라져 나간 다른 job 은 넣지 않는다.
     * 직전 job 을 찾을 수 없으면 거기서 멈춘다.
     */
    @Transactional(readOnly = true)
    public RefinementHistoryResponse getHistory(UUID userId, UUID jobId) {
        Recommendation current = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        List<Recommendation> path = new ArrayList<>();
        Set<UUID> visited = new HashSet<>();
        Recommendation job = current;
        while (job != null && visited.add(job.getId()) && path.size() < MAX_HISTORY_STEPS) {
            path.add(job);
            job = job.getParentJobId() == null ? null
                    : recommendationRepository.findByIdAndUserId(job.getParentJobId(), userId).orElse(null);
        }
        Collections.reverse(path);

        List<Step> steps = new ArrayList<>();
        JsonNode previousQuery = MissingNode.getInstance();
        for (Recommendation step : path) {
            JsonNode result = resultOf(step);
            JsonNode query = result.path("query");
            steps.add(new Step(step.getId(), stepLabel(step), stepDetail(step, previousQuery, query),
                    result.path("items").size(), step.getId().equals(current.getId())));
            previousQuery = query;
        }
        return new RefinementHistoryResponse(steps, null);
    }

    /** 처음 검색이면 "처음 검색", 조건 수정이면 "+ " 뒤에 고른 조건 이름과 직접 쓴 조건 */
    static String stepLabel(Recommendation job) {
        if (job.getParentJobId() == null) {
            return FIRST_STEP_LABEL;
        }
        List<String> parts = new ArrayList<>();
        if (job.getRefinePresets() != null) {
            Arrays.stream(job.getRefinePresets())
                    .map(RefinePreset::fromKey)
                    .flatMap(Optional::stream)
                    .map(RefinePreset::label)
                    .forEach(parts::add);
        }
        if (job.getRefineText() != null && !job.getRefineText().isBlank()) {
            parts.add(job.getRefineText());
        }
        return "+ " + (parts.isEmpty() ? Objects.requireNonNullElse(job.getRawQuery(), "") : String.join(", ", parts));
    }

    /** 처음 검색이면 검색 문장, 나머지는 직전 단계와 달라진 조건. 비교할 수 없으면 그 단계에서 더한 조건 문장 */
    private static String stepDetail(Recommendation job, JsonNode previousQuery, JsonNode query) {
        String rawQuery = Objects.requireNonNullElse(job.getRawQuery(), "");
        if (job.getParentJobId() == null) {
            return rawQuery;
        }
        return Objects.requireNonNullElse(QueryDiff.describe(previousQuery, query), rawQuery);
    }

    /** 결과의 질의 요약으로 만든 조건 칩. 상품 기준 추천(v1) job 이거나 결과가 없거나 읽을 수 없으면 빈 목록 */
    private List<String> currentConditions(Recommendation job) {
        if (job.getBasis() == null || job.getResult() == null) {
            return List.of();
        }
        return SummaryBuilder.conditions(resultOf(job).path("query"));
    }

    /**
     * job 의 결과. 없거나 읽을 수 없으면 MissingNode.
     * 결과는 jsonb 라 깨진 JSON 이 저장될 일은 거의 없고, 한 단계를 읽지 못했다고 이력 전체를 실패시키지 않는다
     */
    private JsonNode resultOf(Recommendation job) {
        try {
            return jsonUtil.readTree(job.getResult());
        } catch (BusinessException e) {
            log.warn("[RecommendationRefine] job 의 결과를 읽지 못해 비어 있는 것으로 본다: jobId={}", job.getId());
            return MissingNode.getInstance();
        }
    }
}
