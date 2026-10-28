package com.capstone.backend.domain.recommendation.dto.request;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

/** 추가 질문 답변. 되묻기에서 물어본 항목의 key 를 키로 하는 답 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ClarificationRequest {

    @NotNull(message = "answers는 필수입니다.")
    @Valid
    private Answers answers;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class Answers {

        /** 예산(원) */
        @Min(value = 1, message = "budget은 1 이상이어야 합니다.")
        private Integer budget;

        /** 세트 구성 단계 */
        private List<String> bundleSteps;

        /** 찾는 종류 */
        private String category;

        /** 기준 제품. 상품 ID 또는 제품 이름 */
        private String baseProduct;

        /** 그 밖의 자유 답변 */
        private String text;

        @JsonIgnore
        @AssertTrue(message = "답을 하나 이상 보내 주세요.")
        public boolean isAnyAnswered() {
            return budget != null
                    || (bundleSteps != null && bundleSteps.stream().anyMatch(step -> step != null && !step.isBlank()))
                    || hasText(category) || hasText(baseProduct) || hasText(text);
        }

        private static boolean hasText(String value) {
            return value != null && !value.isBlank();
        }
    }
}
