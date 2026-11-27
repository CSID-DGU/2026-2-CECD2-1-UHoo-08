package com.capstone.backend.domain.home.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 최근 기간 인기 상승 제품. 개인화하지 않은 전체 공통 순위다 */
@Getter
@AllArgsConstructor
public class TrendProductsResponse {
    /** 순위를 매긴 기간 일수 */
    private int periodDays;
    /** 순위순 */
    private List<Item> items;
    /** 기간 중 트렌드 기록이 마지막으로 갱신된 시각. 기록이 없으면 null */
    private OffsetDateTime updatedAt;

    @Getter
    @AllArgsConstructor
    public static class Item {
        private int rank;
        private UUID productId;
        private String name;
        private String brand;
        /** 최저가, 없으면 정가. 둘 다 없으면 null */
        private Integer price;
        private String imageUrl;
        /** 직전 같은 기간보다 관심이 몇 % 늘었는지. 직전 기간 기록이 없으면 null */
        private Integer interestChangePct;
    }
}
