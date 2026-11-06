package com.capstone.backend.domain.preference.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.preference.dto.response.PreferenceChangeRevertResponse;
import com.capstone.backend.domain.preference.entity.PreferenceWeightChange;
import com.capstone.backend.domain.preference.repository.PreferenceWeightChangeRepository;
import com.capstone.backend.domain.recommendation.service.RecommendationJobService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class PreferenceWeightChangeServiceTest {

    private static final OffsetDateTime NOW = OffsetDateTime.of(2026, 10, 31, 12, 0, 0, 0, ZoneOffset.UTC);

    @Mock
    PreferenceWeightChangeRepository changeRepository;
    @Mock
    RecommendationJobService recommendationJobService;

    PreferenceWeightChangeService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID changeId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new PreferenceWeightChangeService(changeRepository, recommendationJobService);
    }

    /** 행은 AI 만 만들어 엔티티에 생성자가 없다. 저장된 행을 읽어 온 것처럼 값을 채운다 */
    private void givenChange(int reverted) {
        PreferenceWeightChange change = BeanUtils.instantiateClass(PreferenceWeightChange.class);
        ReflectionTestUtils.setField(change, "id", changeId);
        ReflectionTestUtils.setField(change, "userId", userId);
        given(changeRepository.findByIdAndUserId(changeId, userId)).willReturn(Optional.of(change));
        given(changeRepository.markReverted(changeId, NOW)).willReturn(reverted);
    }

    @Test
    void 되돌리면_되돌린_시각을_남기고_AI에_가중치_반영을_알린다() {
        givenChange(1);

        PreferenceChangeRevertResponse response = service.revert(userId, changeId, NOW);

        assertThat(response.getChangeId()).isEqualTo(changeId);
        assertThat(response.isReverted()).isTrue();
        verify(changeRepository).markReverted(changeId, NOW);
        verify(recommendationJobService).requestFeedbackApply(userId);
    }

    @Test
    void 이미_되돌린_변경이면_CHANGE_NOT_REVERTIBLE이다() {
        // 이미 되돌렸거나, 같은 변경을 동시에 되돌린 다른 요청이 먼저 남겼다
        givenChange(0);

        assertThatThrownBy(() -> service.revert(userId, changeId, NOW))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.CHANGE_NOT_REVERTIBLE);
        verifyNoInteractions(recommendationJobService);
    }

    @Test
    void 남의_변경이면_NOT_FOUND다() {
        given(changeRepository.findByIdAndUserId(changeId, userId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.revert(userId, changeId, NOW))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
        verify(changeRepository, never()).markReverted(any(), any());
        verifyNoInteractions(recommendationJobService);
    }
}
