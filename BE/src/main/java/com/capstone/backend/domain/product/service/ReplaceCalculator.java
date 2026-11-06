package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.enums.ReplaceStatus;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Map;

/**
 * 보유 제품의 교체 시기 계산. 규칙 기반이며 DB 를 읽지 않는 순수 계산이다.
 *
 * 기한은 유통기한과 (개봉일 + 개봉 후 사용 기간) 중 이른 날이다. 없는 값은 빼고 계산한다.
 * 둘 다 없으면 개봉일에 카테고리 평균 사용 기간을, 그것도 없으면 12개월을 더한다.
 */
public final class ReplaceCalculator {

    /** 기한까지 이만큼 이하로 남으면 곧 바꿀 때다 */
    static final int SOON_DAYS = 45;
    static final int DEFAULT_MONTHS = 12;

    /**
     * 개봉 후 대략적인 사용 기간(개월). 실제 통계가 없어 화장품 일반 권장 기간으로 잡은 고정값이다.
     * 립 제품은 다른 제품보다 오래 쓰는 편이라 길게 둔다.
     */
    static final Map<String, Integer> CATEGORY_MONTHS = Map.of(
            "base", 12,
            "sun", 12,
            "skincare", 12,
            "lip", 18
    );

    private ReplaceCalculator() {
    }

    /** 계산 결과. progress 는 시작일부터 기한까지 지난 비율(0~100) */
    public record Estimate(ReplaceStatus status, int progress, String text, LocalDate deadline) {
    }

    /**
     * @param startedAt 사용을 시작한 날(개봉일, 없으면 등록일). 경과 비율의 기준이다
     * @param category  products.category. 모르는 값이면 기본 12개월
     */
    public static Estimate estimate(LocalDate startedAt, LocalDate expiryDate, Integer paoMonths,
                                    String category, LocalDate today) {
        LocalDate deadline = deadline(startedAt, expiryDate, paoMonths, category);

        long totalDays = ChronoUnit.DAYS.between(startedAt, deadline);
        long elapsedDays = ChronoUnit.DAYS.between(startedAt, today);
        int progress = totalDays <= 0 ? 100 : clamp(Math.round(elapsedDays * 100.0 / totalDays));

        long remainingDays = ChronoUnit.DAYS.between(today, deadline);
        ReplaceStatus status = remainingDays < 0 ? ReplaceStatus.EXPIRED
                : remainingDays <= SOON_DAYS ? ReplaceStatus.SOON
                : ReplaceStatus.OK;

        return new Estimate(status, progress, text(remainingDays), deadline);
    }

    static LocalDate deadline(LocalDate startedAt, LocalDate expiryDate, Integer paoMonths, String category) {
        LocalDate byPao = paoMonths != null && paoMonths > 0 ? startedAt.plusMonths(paoMonths) : null;
        if (expiryDate != null && byPao != null) {
            return expiryDate.isBefore(byPao) ? expiryDate : byPao;
        }
        if (expiryDate != null) {
            return expiryDate;
        }
        if (byPao != null) {
            return byPao;
        }
        int months = category == null ? DEFAULT_MONTHS : CATEGORY_MONTHS.getOrDefault(category, DEFAULT_MONTHS);
        return startedAt.plusMonths(months);
    }

    /** "3주쯤 남았어요" / "기한이 2주 지났어요". 주 단위로 반올림한다 */
    static String text(long remainingDays) {
        long weeks = Math.round(Math.abs(remainingDays) / 7.0);
        if (remainingDays < 0) {
            return weeks == 0 ? "기한이 지났어요" : "기한이 " + weeks + "주 지났어요";
        }
        return weeks == 0 ? "이번 주 안에 기한이에요" : weeks + "주쯤 남았어요";
    }

    private static int clamp(long value) {
        return (int) Math.max(0, Math.min(100, value));
    }
}
