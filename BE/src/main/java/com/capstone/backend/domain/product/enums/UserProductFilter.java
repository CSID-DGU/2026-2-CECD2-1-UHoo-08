package com.capstone.backend.domain.product.enums;

import java.util.List;

/**
 * 보유 제품 목록의 상태 필터. 버린 제품도 더는 쓰지 않는 제품이라 다 쓴 제품(FINISHED)에 함께 넣는다.
 */
public enum UserProductFilter {

    USING(List.of(UsageType.USING)),
    FINISHED(List.of(UsageType.USED, UsageType.DISCARDED)),
    ALL(List.of(UsageType.values()));

    private final List<UsageType> usageTypes;

    UserProductFilter(List<UsageType> usageTypes) {
        this.usageTypes = usageTypes;
    }

    public List<UsageType> usageTypes() {
        return usageTypes;
    }
}
