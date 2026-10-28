package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.enums.RefinePreset;

import java.util.Arrays;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 최근 job 들의 조건 수정 선택지에서 자주 고른 조건을 찾는다 */
public final class RefinePresetCounter {

    /** 이 횟수 이상 고르면 자주 고른 조건이다 */
    static final int FREQUENT_COUNT = 2;

    private RefinePresetCounter() {
    }

    /** job 마다 고른 선택지 목록에서 두 번 이상 나온 조건. 모르는 키는 건너뛴다 */
    public static Set<RefinePreset> frequent(List<String[]> presetsPerJob) {
        Map<RefinePreset, Integer> counts = new EnumMap<>(RefinePreset.class);
        for (String[] presets : presetsPerJob) {
            if (presets == null) {
                continue;
            }
            // 한 job 에서 같은 키가 두 번 들어 있어도 한 번 고른 것으로 센다
            Arrays.stream(presets)
                    .filter(Objects::nonNull)
                    .distinct()
                    .forEach(key -> RefinePreset.fromKey(key).ifPresent(preset -> counts.merge(preset, 1, Integer::sum)));
        }
        Set<RefinePreset> frequent = EnumSet.noneOf(RefinePreset.class);
        counts.forEach((preset, count) -> {
            if (count >= FREQUENT_COUNT) {
                frequent.add(preset);
            }
        });
        return frequent;
    }
}
