package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.preference.entity.PreferenceWeightChange;
import com.capstone.backend.domain.preference.repository.PreferenceWeightChangeRepository;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.AppliedPreference;
import org.junit.jupiter.api.Test;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

class AppliedPreferenceFinderTest {

    private static final OffsetDateTime NOW = OffsetDateTime.of(2026, 10, 27, 9, 0, 0, 0, ZoneOffset.UTC);

    private final PreferenceWeightChangeRepository repository = mock(PreferenceWeightChangeRepository.class);
    private final AppliedPreferenceFinder finder = new AppliedPreferenceFinder(repository);
    private final UUID userId = UUID.randomUUID();

    @Test
    void 최근_14일_안에_되돌리지_않은_가장_최근_변경의_문구와_ID를_보여_준다() {
        UUID changeId = UUID.randomUUID();
        PreferenceWeightChange change = mock(PreferenceWeightChange.class);
        given(change.getId()).willReturn(changeId);
        given(change.getText()).willReturn("'너무 비싸요' 피드백으로 가격 비중 ↑");
        given(repository.findFirstByUserIdAndRevertedAtIsNullAndCreatedAtAfterOrderByCreatedAtDesc(userId, NOW.minusDays(14)))
                .willReturn(Optional.of(change));

        AppliedPreference applied = finder.find(userId, NOW);

        assertThat(applied.getText()).isEqualTo("'너무 비싸요' 피드백으로 가격 비중 ↑");
        assertThat(applied.getChangeId()).isEqualTo(changeId);
    }

    @Test
    void 보여_줄_변경이_없으면_null이다() {
        // 되돌린 변경과 14일 전 변경은 조회 조건에서 빠진다
        given(repository.findFirstByUserIdAndRevertedAtIsNullAndCreatedAtAfterOrderByCreatedAtDesc(userId, NOW.minusDays(14)))
                .willReturn(Optional.empty());

        assertThat(finder.find(userId, NOW)).isNull();
    }
}
