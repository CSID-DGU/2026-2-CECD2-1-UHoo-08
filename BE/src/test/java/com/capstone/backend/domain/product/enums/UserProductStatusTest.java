package com.capstone.backend.domain.product.enums;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;

import static org.assertj.core.api.Assertions.assertThat;

class UserProductStatusTest {

    @ParameterizedTest
    @CsvSource({
            "USING, USING",
            "USED, FINISHED",
            "DISCARDED, DISCARDED",
    })
    void usage_type과_API_상태는_하나씩_짝이_맞는다(UsageType usageType, UserProductStatus status) {
        assertThat(UserProductStatus.from(usageType)).isEqualTo(status);
        assertThat(status.usageType()).isEqualTo(usageType);
    }

    @ParameterizedTest
    @EnumSource(UsageType.class)
    void 모든_usage_type은_API_상태로_바뀐다(UsageType usageType) {
        // DB CHECK 가 허용하는 값은 전부 API 상태가 있어야 목록 조회가 실패하지 않는다
        assertThat(UserProductStatus.from(usageType).usageType()).isEqualTo(usageType);
    }
}
