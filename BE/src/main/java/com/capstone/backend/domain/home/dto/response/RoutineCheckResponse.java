package com.capstone.backend.domain.home.dto.response;

import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/** 쓰는 제품끼리 성분 충돌을 검사한 결과와, 같이 쓰면 안 되는 쌍의 대체 추천 */
@Getter
@AllArgsConstructor
public class RoutineCheckResponse {
    /** AI 루틴 점검 결과가 있는지. false 면 아직 점검 전이라 쌍과 개수가 비어 있다 */
    private boolean checked;
    /** 쓰는 중인 보유 제품 수 */
    private int productCount;
    private Counts counts;
    /** 같이 쓰지 말 것 → 시간 나눠 쓸 것 → 괜찮음 순. 보유 제품이 2개 미만이면 빈 배열 */
    private List<Pair> pairs;
    /** 같이 쓰지 말 쌍이 있을 때의 대체 제안. 없으면 null */
    private Replacement replacement;
    private Schedule schedule;
    /** 성분 정보가 없어 비교하지 못한 제품 수 */
    private int uncomparedCount;

    @Getter
    @AllArgsConstructor
    public static class Counts {
        private int ok;
        private int separate;
        private int avoid;
    }

    @Getter
    @AllArgsConstructor
    public static class Pair {
        private UserProductRef a;
        private UserProductRef b;
        private CompatibilityLevel level;
        /** 예: 같이 쓰지 마세요 */
        private String title;
        private String reason;
    }

    @Getter
    @AllArgsConstructor
    public static class UserProductRef {
        private String userProductId;
        private String name;
    }

    @Getter
    @AllArgsConstructor
    public static class Replacement {
        /** 바꾸길 권하는 보유 제품 */
        private UserProductRef replaceTarget;
        private String message;
        /** 나머지 보유 제품과 모두 괜찮은 대체 후보 */
        private List<ReplacementItem> items;
    }

    @Getter
    @AllArgsConstructor
    public static class ReplacementItem {
        private String productId;
        private String name;
        private String brand;
        private Integer price;
        private Integer totalScore;
        /** 예: 쓰시는 제품 5개와 모두 괜찮아요 */
        private String badge;
    }

    @Getter
    @AllArgsConstructor
    public static class Schedule {
        private List<String> morning;
        private List<String> evening;
        /** 순서 팁. 없으면 null */
        private String tip;
    }
}
