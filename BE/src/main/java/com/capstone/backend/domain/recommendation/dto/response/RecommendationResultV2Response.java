package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

/** 자연어 추천 결과. 검색 결과, 결과 보고서, 조건 수정, 예산 세트, 홈 추천이 모두 이 모양이다 */
@Getter
@AllArgsConstructor
public class RecommendationResultV2Response implements RecommendationResultBody {

    private UUID jobId;
    /** 조건 수정으로 만들어진 결과면 직전 job */
    private UUID parentJobId;
    private String scenario;
    private RecommendationBasis basis;
    private Summary summary;
    /** 개인화 가중치가 반영됐을 때 안내. 없으면 null */
    private AppliedPreference appliedPreference;
    private List<Item> items;
    private Excluded excluded;
    private List<Alternative> alternatives;
    /** 점수 기준 미달로 뺀 대체 후보 수 */
    private int alternativesDroppedCount;
    private List<SimilarUserProduct> similarUserProducts;
    private List<Bundle> bundles;

    /** 결과 상단 문구 */
    @Getter
    @AllArgsConstructor
    public static class Summary {
        /** 비어 있거나 모르는 카테고리면 null */
        private String categoryLabel;
        private int totalCount;
        /** 오른쪽 위 기준 문구 */
        private String basisLabel;
        /** 적용 조건 칩 */
        private List<String> conditions;
        /** 가성비, 환경 등 기준 설명. 없으면 null */
        private String notice;
    }

    /** 결과 보고서의 되돌리기 안내 */
    @Getter
    @AllArgsConstructor
    public static class AppliedPreference {
        private String text;
        private UUID changeId;
    }

    @Getter
    @AllArgsConstructor
    public static class Item {
        private String productId;
        private String name;
        private String brand;
        private String imageUrl;
        private Integer price;
        /** 0~100. 인기 기준이면 null */
        private Integer totalScore;
        /** 인기 기준일 때만 */
        private Double rating;
        /** 인기 기준일 때만 */
        private Integer reviewCount;
        /** 점수 분해. 항목 수가 바뀔 수 있다 */
        private List<ScoreItem> breakdown;
        private List<Badge> badges;
        private String reason;
        /** 조건 수정 결과에서만. NEW, SAME, UP, DOWN */
        private String change;
        /** 순위 변화. 올라가면 양수 */
        private Integer rankDelta;
    }

    @Getter
    @AllArgsConstructor
    public static class ScoreItem {
        private String key;
        private String label;
        private Double score;
        private Double weight;
    }

    @Getter
    @AllArgsConstructor
    public static class Badge {
        private String type;
        private String text;
    }

    /** 걸러낸 제품 */
    @Getter
    @AllArgsConstructor
    public static class Excluded {
        private int count;
        private List<ExcludedItem> items;
    }

    @Getter
    @AllArgsConstructor
    public static class ExcludedItem {
        private String productId;
        private String name;
        /** OWNED, CONFLICT */
        private String reason;
        private String detail;
    }

    /** 상품 평가의 비슷한 대체 상품 */
    @Getter
    @AllArgsConstructor
    public static class Alternative {
        private String productId;
        private String name;
        private String brand;
        private Integer price;
        /** AI 가 점수 분해에 유사도를 넣었을 때만. 없으면 null */
        private Double similarity;
        private Integer totalScore;
    }

    /** 비슷한 사용자들이 쓰는 제품 */
    @Getter
    @AllArgsConstructor
    public static class SimilarUserProduct {
        private String productId;
        private String name;
        private String brand;
        private Integer price;
    }

    /** 예산 세트 조합 하나 */
    @Getter
    @AllArgsConstructor
    public static class Bundle {
        /** 1부터 */
        private int index;
        /** 조합 유형. AI 가 칸 정보를 주기 전까지 null */
        private String type;
        private String label;
        private int total;
        /** 예산 - 합계. 예산이 없으면 null */
        private Integer remaining;
        private int totalScore;
        private List<Slot> slots;
    }

    @Getter
    @AllArgsConstructor
    public static class Slot {
        /** 칸 키. AI 가 칸 정보를 주기 전까지 칸 순서("0", "1", ...) */
        private String slotKey;
        /** 칸 이름. AI 가 칸 정보를 주기 전까지 null */
        private String label;
        private String productId;
        private String name;
        private Integer price;
        private Integer score;
    }
}
