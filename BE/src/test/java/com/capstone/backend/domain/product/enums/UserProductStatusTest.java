package com.capstone.backend.domain.product.enums;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;

class UserProductStatusTest {

    @ParameterizedTest
    @CsvSource({
            "USING, USING",
            "ONBOARDING, USING",
            "USED, FINISHED",
            "DISCARDED, DISCARDED",
    })
    void 저장된_usage_type을_API_상태로_바꾼다(String usageType, UserProductStatus expected) {
        assertThat(UserProductStatus.fromUsageType(usageType)).contains(expected);
        assertThat(UserProductStatus.fromUsageType(UsageType.valueOf(usageType))).contains(expected);
    }

    @ParameterizedTest
    @NullSource
    @ValueSource(strings = {"VIEWED", "INTERESTED", "using", "UNKNOWN", ""})
    void 보유가_아니거나_모르는_값은_상태가_없다(String usageType) {
        assertThat(UserProductStatus.fromUsageType(usageType)).isEmpty();
    }

    @Test
    void 상태를_바꿀_때_저장할_usage_type() {
        assertThat(UserProductStatus.USING.storedUsageType()).isEqualTo(UsageType.USING);
        assertThat(UserProductStatus.FINISHED.storedUsageType()).isEqualTo(UsageType.USED);
        assertThat(UserProductStatus.DISCARDED.storedUsageType()).isEqualTo(UsageType.DISCARDED);
    }

    @Test
    void USING_상태는_온보딩에서_등록한_것까지_찾는다() {
        assertThat(UserProductStatus.USING.usageTypes()).containsExactly(UsageType.USING, UsageType.ONBOARDING);
        assertThat(UserProductStatus.FINISHED.usageTypes()).containsExactly(UsageType.USED);
    }

    @Test
    void 조회_이력과_위시리스트는_어느_상태에도_속하지_않는다() {
        for (UserProductStatus status : UserProductStatus.values()) {
            assertThat(status.usageTypes()).doesNotContain(UsageType.VIEWED, UsageType.INTERESTED);
        }
    }
}
