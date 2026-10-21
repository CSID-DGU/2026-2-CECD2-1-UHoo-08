package com.capstone.backend.domain.product.dto.response;

import com.capstone.backend.domain.product.enums.ReplaceStatus;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/** 보유 제품 목록. 보관 위치는 쓰지 않는 기능이라 넣지 않는다 */
@Getter
@AllArgsConstructor
public class UserProductListResponse {
    private List<Item> items;
    private ConflictSummary conflictSummary;
    /** 전체 개수. 응답의 meta 로 나간다 */
    @JsonIgnore
    private long total;

    @Getter
    @AllArgsConstructor
    public static class Item {
        private UUID userProductId;
        private UUID productId;
        private String name;
        private String brand;
        private String imageUrl;
        private LocalDate openedAt;
        private Integer remainingPct;
        private ReplaceStatus replaceStatus;
        private String replaceText;
        /** 막대 길이 0~100 */
        private int replaceProgress;
        /** 이 제품의 충돌 한 줄. 루틴 점검 결과가 연결되기 전까지 null */
        private String conflictText;
    }

    /** 상단 배너. avoidCount 가 0 보다 크면 빨간 배너를 띄운다 */
    @Getter
    @AllArgsConstructor
    public static class ConflictSummary {
        private int avoidCount;
        private String text;

        public static ConflictSummary none() {
            return new ConflictSummary(0, null);
        }
    }
}
