package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.entity.Recommendation;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** 자연어 추천 job 의 진행 상태. 기존 응답에 시나리오·진행 단계·되묻기를 더한다 */
@Getter
public class RecommendationStatusV2Response extends RecommendationStatusResponse {
    /** 판정된 시나리오. 판정 전이면 null */
    private final String scenario;
    private final List<Step> steps;
    /** 되묻는 중일 때만 값이 있다 */
    private final Clarify clarify;

    public RecommendationStatusV2Response(Recommendation r, List<Step> steps, Clarify clarify) {
        super(r);
        this.scenario = r.getScenario();
        this.steps = steps;
        this.clarify = clarify;
    }

    @Getter
    @AllArgsConstructor
    public static class Step {
        private String key;
        private String label;
        /** DONE, NOW, TODO */
        private String state;
    }

    @Getter
    @AllArgsConstructor
    public static class Clarify {
        private String message;
        private List<ClarifyFieldResponse> fields;
    }
}
