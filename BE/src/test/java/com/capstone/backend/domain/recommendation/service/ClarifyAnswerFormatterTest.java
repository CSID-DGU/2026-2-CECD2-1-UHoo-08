package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.request.ClarificationRequest.Answers;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ClarifyAnswerFormatterTest {

    @Test
    void 예산과_구성은_예산_원_구성_순으로_합친다() {
        Answers answers = Answers.builder().budget(50000).bundleSteps(List.of("스킨", "로션")).build();

        assertThat(ClarifyAnswerFormatter.format(answers, null)).isEqualTo("예산 50000원, 구성: 스킨, 로션");
    }

    @Test
    void 종류_기준_제품_자유_답변을_뒤에_붙인다() {
        Answers answers = Answers.builder().category(" 쿠션 ").baseProduct("11111111-1111-1111-1111-111111111111")
                .text("여름에 쓸 거예요").build();

        assertThat(ClarifyAnswerFormatter.format(answers, "베어 워터 쿠션"))
                .isEqualTo("종류: 쿠션, 기준 제품: 베어 워터 쿠션, 여름에 쓸 거예요");
    }

    @Test
    void 구성의_빈_항목은_건너뛰고_앞뒤_공백을_지운다() {
        Answers answers = Answers.builder().bundleSteps(Arrays.asList(" 스킨", "", null, "선크림 ")).build();

        assertThat(ClarifyAnswerFormatter.format(answers, null)).isEqualTo("구성: 스킨, 선크림");
    }

    @Test
    void 자유_답변만_있으면_그대로_보낸다() {
        assertThat(ClarifyAnswerFormatter.format(Answers.builder().text("민감한 피부예요").build(), null))
                .isEqualTo("민감한 피부예요");
    }

    @Test
    void 비어_있는_답은_모두_건너뛴다() {
        Answers answers = Answers.builder().budget(30000).bundleSteps(List.of(" ")).category("").text("  ").build();

        assertThat(ClarifyAnswerFormatter.format(answers, null)).isEqualTo("예산 30000원");
    }

    @Test
    void 답이_하나라도_있어야_받는다() {
        assertThat(Answers.builder().build().isAnyAnswered()).isFalse();
        assertThat(Answers.builder().bundleSteps(List.of(" ")).text(" ").build().isAnyAnswered()).isFalse();
        assertThat(Answers.builder().budget(10000).build().isAnyAnswered()).isTrue();
        assertThat(Answers.builder().baseProduct("쿠션").build().isAnyAnswered()).isTrue();
    }
}
