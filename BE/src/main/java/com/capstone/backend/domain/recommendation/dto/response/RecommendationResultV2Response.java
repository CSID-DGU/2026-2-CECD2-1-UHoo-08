package com.capstone.backend.domain.recommendation.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** 자연어 추천 결과. 검색 결과, 결과 보고서, 조건 수정, 예산 세트, 홈 추천이 모두 이 모양이다 */
@Getter
@AllArgsConstructor
public class RecommendationResultV2Response {

    private Summary summary;

    /** 결과 상단 문구 */
    @Getter
    @AllArgsConstructor
    public static class Summary {
        /** 비어 있거나 모르는 카테고리면 null */
        private String categoryLabel;
        private int totalCount;
        /** 오른쪽 위 기준 문구 */
        private String basisLabel;
        /** 적용 조건 칩 */
        private List<String> conditions;
        /** 가성비, 환경 등 기준 설명. 없으면 null */
        private String notice;
    }
}
