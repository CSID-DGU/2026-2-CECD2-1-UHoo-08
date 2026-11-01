package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.config.HwadamProperties.EnvThresholds;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.SeasonChange;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Stats;
import com.capstone.backend.domain.home.entity.EnvDaily;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.EnvDailyRepository;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.OptionalDouble;
import java.util.UUID;

/**
 * 사용자 지역의 최근 4주 환경 요약.
 *
 * 하루 환경 집계는 AI 가 쓰고 BE 는 읽어서 센다. 관측이 없는 날(sample_count=0)은 "괜찮은 날"로 세지 않도록 아예 뺀다.
 * 환경이 요구하는 제품 조건과 보유 제품이 채우는지는 AI 홈 환경 추천 결과에서 읽는다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EnvironmentService {

    /** 오늘을 포함해 거슬러 올라가는 날 수 */
    static final int PERIOD_DAYS = 28;
    /** 계절 전환에서 비교하는 한 주의 날 수 */
    static final int WEEK_DAYS = 7;
    static final String SEASON_CHANGE_TITLE = "계절이 바뀌고 있어요";

    private final UserRepository userRepository;
    private final EnvDailyRepository envDailyRepository;
    private final HomeRecommendationRepository homeRecommendationRepository;
    private final HwadamProperties hwadamProperties;
    private final JsonUtil jsonUtil;

    /** 지역을 설정하지 않았으면 REGION_NOT_SET */
    @Transactional(readOnly = true)
    public EnvironmentSummaryResponse getSummary(UUID userId) {
        return getSummary(userId, LocalDate.now(hwadamProperties.getBatch().getZone()));
    }

    EnvironmentSummaryResponse getSummary(UUID userId, LocalDate today) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        if (user.getRegion() == null || user.getRegion().isBlank()) {
            throw new BusinessException(ErrorCode.REGION_NOT_SET);
        }

        LocalDate periodStart = today.minusDays(PERIOD_DAYS - 1);
        List<EnvDaily> rows = envDailyRepository.findByRegionAndDateBetween(user.getRegion(), periodStart, today);
        List<EnvDaily> observed = rows.stream().filter(day -> day.getSampleCount() > 0).toList();

        Optional<HomeRecommendation> recommendation = homeRecommendationRepository.findById(
                new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV));
        List<Condition> conditions = recommendation.map(found -> conditions(found, userId)).orElseGet(List::of);
        return new EnvironmentSummaryResponse(
                user.getRegionLabel() != null ? user.getRegionLabel() : user.getRegion(),
                periodStart,
                today,
                observed.size(),
                stats(observed),
                seasonChange(observed, today),
                recommendation.isPresent(),
                conditions,
                (int) conditions.stream().filter(condition -> !condition.isCovered()).count(),
                rows.stream().map(EnvDaily::getUpdatedAt).filter(Objects::nonNull)
                        .max(Comparator.naturalOrder()).orElse(null));
    }

    private Stats stats(List<EnvDaily> observed) {
        EnvThresholds thresholds = hwadamProperties.getEnv();
        int uvHighDays = (int) observed.stream()
                .filter(day -> day.getUvMax() != null && day.getUvMax() >= thresholds.getUvHigh())
                .count();
        int dustBadDays = (int) observed.stream()
                .filter(day -> (day.getPm10Avg() != null && day.getPm10Avg() > thresholds.getPm10Bad())
                        || (day.getPm25Avg() != null && day.getPm25Avg() > thresholds.getPm25Bad()))
                .count();
        OptionalDouble humidity = averageHumidity(observed);
        return new Stats(uvHighDays, dustBadDays,
                humidity.isPresent() ? (int) Math.round(humidity.getAsDouble()) : null);
    }

    /**
     * 최근 7일 평균 습도가 3주 전 7일(21~27일 전) 평균보다 기준 이상 다르면 계절 전환으로 본다.
     * 두 주 중 한쪽이라도 습도 기록이 없으면 비교하지 않는다.
     */
    private SeasonChange seasonChange(List<EnvDaily> observed, LocalDate today) {
        LocalDate recentStart = today.minusDays(WEEK_DAYS - 1);
        LocalDate pastStart = today.minusDays(PERIOD_DAYS - 1);
        LocalDate pastEnd = pastStart.plusDays(WEEK_DAYS - 1);
        OptionalDouble recent = averageHumidity(observed.stream()
                .filter(day -> !day.getDate().isBefore(recentStart)).toList());
        OptionalDouble past = averageHumidity(observed.stream()
                .filter(day -> !day.getDate().isAfter(pastEnd)).toList());
        if (recent.isEmpty() || past.isEmpty()
                || Math.abs(recent.getAsDouble() - past.getAsDouble()) < hwadamProperties.getEnv().getHumidityChange()) {
            return null;
        }
        String direction = recent.getAsDouble() < past.getAsDouble() ? "떨어졌어요" : "올랐어요";
        return new SeasonChange(SEASON_CHANGE_TITLE, "습도가 3주 만에 " + Math.round(past.getAsDouble()) + "% → "
                + Math.round(recent.getAsDouble()) + "%로 " + direction);
    }

    private static OptionalDouble averageHumidity(List<EnvDaily> days) {
        return days.stream().map(EnvDaily::getHumidityAvg).filter(Objects::nonNull).mapToDouble(Float::doubleValue).average();
    }

    /** AI 홈 환경 추천 결과의 조건 목록. 조건 블록이 없으면 빈 목록 */
    private List<Condition> conditions(HomeRecommendation recommendation, UUID userId) {
        JsonNode items = readTree(recommendation.getResult(), userId).path("conditions");
        List<Condition> conditions = new ArrayList<>();
        if (!items.isArray()) {
            return conditions;
        }
        items.forEach(item -> {
            String key = item.path("key").asText(null);
            if (key == null || key.isBlank()) {
                return;
            }
            conditions.add(new Condition(key, item.path("label").asText(key), item.path("basis").asText(null),
                    item.path("covered").asBoolean(false), item.path("coveredBy").asText(null)));
        });
        return conditions;
    }

    private JsonNode readTree(String json, UUID userId) {
        try {
            return jsonUtil.readTree(json);
        } catch (BusinessException e) {
            log.warn("[Environment] 홈 환경 추천 결과를 읽지 못해 조건을 비워 둔다: userId={}", userId);
            return MissingNode.getInstance();
        }
    }
}
