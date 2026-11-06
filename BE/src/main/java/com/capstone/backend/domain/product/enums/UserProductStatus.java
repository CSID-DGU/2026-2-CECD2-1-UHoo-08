package com.capstone.backend.domain.product.enums;

import java.util.Arrays;

/**
 * 보유 제품 API 의 status 와 user_products.usage_type 의 대응. 하나씩 짝이 맞는다.
 *
 *   USING      ↔ USING
 *   FINISHED   ↔ USED
 *   DISCARDED  ↔ DISCARDED
 *
 * DB 값 이름(USED)은 AI 코드가 함께 쓰고 있어 그대로 두고, API 에서만 FINISHED 로 내보낸다.
 */
public enum UserProductStatus {

    USING(UsageType.USING),
    FINISHED(UsageType.USED),
    DISCARDED(UsageType.DISCARDED);

    private final UsageType usageType;

    UserProductStatus(UsageType usageType) {
        this.usageType = usageType;
    }

    /** 이 상태로 바꾸거나 조회할 때 쓰는 usage_type */
    public UsageType usageType() {
        return usageType;
    }

    /** usage_type 을 API 상태로 바꾼다 */
    public static UserProductStatus from(UsageType usageType) {
        return Arrays.stream(values())
                .filter(status -> status.usageType == usageType)
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("알 수 없는 usage_type: " + usageType));
    }
}
