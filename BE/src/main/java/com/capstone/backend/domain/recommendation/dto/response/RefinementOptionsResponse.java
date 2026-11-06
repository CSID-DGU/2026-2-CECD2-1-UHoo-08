package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** '어떤 조건을 더할까요?' 시트에 보여줄 지금 조건과 고를 수 있는 조건 */
@Getter
@AllArgsConstructor
public class RefinementOptionsResponse {
    /** 지금 조건 칩. 결과 상단의 조건 칩과 같다 */
    private List<String> currentConditions;
    private List<Preset> presets;

    @Getter
    @AllArgsConstructor
    public static class Preset {
        private RefinePreset key;
        private String label;
        /** 최근 30일 동안 두 번 이상 고른 조건 */
        private boolean frequent;
    }
}
