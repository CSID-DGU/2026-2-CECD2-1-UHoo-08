package com.capstone.backend.domain.product.enums;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

/**
 * 보유 제품 API 의 status 와 user_products.usage_type 의 대응.
 *
 *   USING      ← USING, ONBOARDING (온보딩에서 등록한 것도 쓰고 있는 것으로 본다)
 *   FINISHED   ← USED
 *   DISCARDED  ← DISCARDED
 *
 * VIEWED(조회 이력)와 INTERESTED(위시리스트)는 보유가 아니라 어느 상태에도 대응하지 않는다.
 * 보유 제품 API 에 이 둘이 나오면 안 된다.
 */
public enum UserProductStatus {

    USING(UsageType.USING, List.of(UsageType.USING, UsageType.ONBOARDING)),
    FINISHED(UsageType.USED, List.of(UsageType.USED)),
    DISCARDED(UsageType.DISCARDED, List.of(UsageType.DISCARDED));

    private final UsageType storedUsageType;
    private final List<UsageType> usageTypes;

    UserProductStatus(UsageType storedUsageType, List<UsageType> usageTypes) {
        this.storedUsageType = storedUsageType;
        this.usageTypes = usageTypes;
    }

    /** 이 상태로 바꿀 때 저장할 usage_type */
    public UsageType storedUsageType() {
        return storedUsageType;
    }

    /** 이 상태로 조회할 때 찾을 usage_type 들 */
    public List<UsageType> usageTypes() {
        return usageTypes;
    }

    /** usage_type 을 API 상태로 바꾼다. 보유가 아니면 비어 있다 */
    public static Optional<UserProductStatus> fromUsageType(UsageType usageType) {
        return Arrays.stream(values())
                .filter(status -> status.usageTypes.contains(usageType))
                .findFirst();
    }

    /** 저장된 문자열(user_products.usage_type)을 API 상태로 바꾼다. 보유가 아니거나 모르는 값이면 비어 있다 */
    public static Optional<UserProductStatus> fromUsageType(String usageType) {
        return Arrays.stream(UsageType.values())
                .filter(type -> type.name().equals(usageType))
                .findFirst()
                .flatMap(UserProductStatus::fromUsageType);
    }
}
