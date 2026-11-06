package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.enums.ReplaceStatus;
import com.capstone.backend.domain.product.service.ReplaceCalculator.Estimate;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class ReplaceCalculatorTest {

    private static final LocalDate OPENED = LocalDate.of(2026, 1, 1);

    @Test
    void 유통기한만_있으면_유통기한이_기한이다() {
        Estimate estimate = ReplaceCalculator.estimate(OPENED, LocalDate.of(2026, 12, 31), null, "skincare",
                LocalDate.of(2026, 7, 2));

        assertThat(estimate.deadline()).isEqualTo(LocalDate.of(2026, 12, 31));
        assertThat(estimate.status()).isEqualTo(ReplaceStatus.OK);
        assertThat(estimate.progress()).isEqualTo(50);
        assertThat(estimate.text()).isEqualTo("26주쯤 남았어요");
    }

    @Test
    void 개봉_후_사용_기간만_있으면_개봉일에_더한_날이_기한이다() {
        Estimate estimate = ReplaceCalculator.estimate(OPENED, null, 6, "skincare", LocalDate.of(2026, 6, 10));

        assertThat(estimate.deadline()).isEqualTo(LocalDate.of(2026, 7, 1));
        assertThat(estimate.status()).isEqualTo(ReplaceStatus.SOON);
        assertThat(estimate.text()).isEqualTo("3주쯤 남았어요");
    }

    @Test
    void 둘_다_있으면_이른_쪽이_기한이다() {
        assertThat(ReplaceCalculator.deadline(OPENED, LocalDate.of(2027, 1, 1), 6, "skincare"))
                .isEqualTo(LocalDate.of(2026, 7, 1));
        assertThat(ReplaceCalculator.deadline(OPENED, LocalDate.of(2026, 3, 1), 12, "skincare"))
                .isEqualTo(LocalDate.of(2026, 3, 1));
    }

    @ParameterizedTest
    @CsvSource({
            "base, 2027-01-01",
            "sun, 2027-01-01",
            "skincare, 2027-01-01",
            "lip, 2027-07-01",
            // 모르는 카테고리는 12개월
            "nail, 2027-01-01",
    })
    void 둘_다_없으면_카테고리_평균_사용_기간을_쓴다(String category, LocalDate expected) {
        assertThat(ReplaceCalculator.deadline(OPENED, null, null, category)).isEqualTo(expected);
    }

    @Test
    void 카테고리도_없으면_12개월이다() {
        assertThat(ReplaceCalculator.deadline(OPENED, null, null, null)).isEqualTo(LocalDate.of(2027, 1, 1));
    }

    @Test
    void 기한이_지났으면_EXPIRED이고_경과는_100으로_자른다() {
        Estimate estimate = ReplaceCalculator.estimate(OPENED, LocalDate.of(2026, 6, 1), null, "skincare",
                LocalDate.of(2026, 6, 15));

        assertThat(estimate.status()).isEqualTo(ReplaceStatus.EXPIRED);
        assertThat(estimate.progress()).isEqualTo(100);
        assertThat(estimate.text()).isEqualTo("기한이 2주 지났어요");
    }

    @Test
    void 남은_날이_45일이면_SOON이고_46일이면_OK다() {
        LocalDate deadline = LocalDate.of(2026, 12, 31);
        assertThat(ReplaceCalculator.estimate(OPENED, deadline, null, null, deadline.minusDays(45)).status())
                .isEqualTo(ReplaceStatus.SOON);
        assertThat(ReplaceCalculator.estimate(OPENED, deadline, null, null, deadline.minusDays(46)).status())
                .isEqualTo(ReplaceStatus.OK);
    }

    @Test
    void 기한_당일은_아직_지나지_않았다() {
        LocalDate deadline = LocalDate.of(2026, 12, 31);
        Estimate estimate = ReplaceCalculator.estimate(OPENED, deadline, null, null, deadline);

        assertThat(estimate.status()).isEqualTo(ReplaceStatus.SOON);
        assertThat(estimate.progress()).isEqualTo(100);
        assertThat(estimate.text()).isEqualTo("이번 주 안에 기한이에요");
    }

    @Test
    void 시작일보다_먼저_기한이면_경과는_100이다() {
        Estimate estimate = ReplaceCalculator.estimate(OPENED, OPENED.minusDays(10), null, null, OPENED);

        assertThat(estimate.progress()).isEqualTo(100);
        assertThat(estimate.status()).isEqualTo(ReplaceStatus.EXPIRED);
    }

    @ParameterizedTest
    @CsvSource({
            "3, 이번 주 안에 기한이에요",
            "4, 1주쯤 남았어요",
            "21, 3주쯤 남았어요",
            "-1, 기한이 지났어요",
            "-11, 기한이 2주 지났어요",
    })
    void 문구는_주_단위로_반올림한다(long remainingDays, String expected) {
        assertThat(ReplaceCalculator.text(remainingDays)).isEqualTo(expected);
    }
}
