package com.capstone.backend.domain.recommendation.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** 예산 세트의 한 칸을 바꿀 때 고를 수 있는 후보와 바꿨을 때의 총액 */
@Getter
@AllArgsConstructor
public class BundleSlotOptionsResponse {
    /** 예산이 없는 결과면 null */
    private Integer budget;
    private int currentTotal;
    /** 적합도순 */
    private List<Option> options;

    @Getter
    @AllArgsConstructor
    public static class Option {
        private String productId;
        private String name;
        private int price;
        private Integer score;
        /** 바꿨을 때 총액 */
        private int newTotal;
        /** 남는 예산. 음수면 초과이고, 예산이 없는 결과면 null */
        private Integer remaining;
        @JsonProperty("isCurrent")
        private boolean current;
        /** 예산 안이면 true */
        private boolean selectable;
        /** 초과 금액. 선택할 수 있으면 null */
        private Integer overBudgetBy;
    }
}
