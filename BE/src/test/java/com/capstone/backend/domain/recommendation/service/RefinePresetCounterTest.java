package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class RefinePresetCounterTest {

    @Test
    void 두_번_이상_고른_조건만_자주_고른_조건이다() {
        List<String[]> presets = List.of(
                new String[]{"CHEAPER", "UNSCENTED"},
                new String[]{"CHEAPER"},
                new String[]{"UV_PROTECT"});

        assertThat(RefinePresetCounter.frequent(presets)).containsExactly(RefinePreset.CHEAPER);
    }

    @Test
    void 한_job에서_같은_키가_겹쳐도_한_번으로_센다() {
        assertThat(RefinePresetCounter.frequent(List.<String[]>of(new String[]{"CHEAPER", "CHEAPER"}))).isEmpty();
    }

    @Test
    void 모르는_키와_빈_값은_건너뛴다() {
        List<String[]> presets = Arrays.asList(
                new String[]{"CHEAPEST", null},
                new String[]{"CHEAPEST"},
                null);

        assertThat(RefinePresetCounter.frequent(presets)).isEmpty();
    }

    @Test
    void 고른_조건이_없으면_비어_있다() {
        assertThat(RefinePresetCounter.frequent(List.of())).isEmpty();
    }

    @Test
    void 조건마다_이름과_AI에_보낼_문장이_있다() {
        assertThat(RefinePreset.CHEAPER.label()).isEqualTo("더 저렴하게");
        assertThat(RefinePreset.CHEAPER.sentence()).isEqualTo("더 저렴한 제품으로");
        assertThat(RefinePreset.SENSITIVE_OK.sentence()).isEqualTo("민감한 피부에도 괜찮은 제품으로");
        assertThat(RefinePreset.fromKey("UV_PROTECT")).contains(RefinePreset.UV_PROTECT);
        assertThat(RefinePreset.fromKey("uv_protect")).isEmpty();
    }
}
