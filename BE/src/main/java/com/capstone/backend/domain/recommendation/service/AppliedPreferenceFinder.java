package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.preference.repository.PreferenceWeightChangeRepository;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.AppliedPreference;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 결과 보고서의 개인화 안내. 최근에 반영된 가중치 변경을 보여 주고 되돌릴 수 있게 한다.
 *
 * 변경은 AI 가 만든다. BE 는 최근 14일 안에 생겨 아직 되돌리지 않은 것 중 가장 최근 것만 읽는다.
 * 오래된 변경까지 보여 주면 이번 결과와 상관없는 안내가 계속 붙는다.
 */
@Component
@RequiredArgsConstructor
public class AppliedPreferenceFinder {

    static final Duration WINDOW = Duration.ofDays(14);

    private final PreferenceWeightChangeRepository preferenceWeightChangeRepository;

    /** 보여 줄 변경이 없으면 null */
    public AppliedPreference find(UUID userId) {
        return find(userId, OffsetDateTime.now());
    }

    AppliedPreference find(UUID userId, OffsetDateTime now) {
        return preferenceWeightChangeRepository
                .findFirstByUserIdAndRevertedAtIsNullAndCreatedAtAfterOrderByCreatedAtDesc(userId, now.minus(WINDOW))
                .map(change -> new AppliedPreference(change.getText(), change.getId()))
                .orElse(null);
    }
}
