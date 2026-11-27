package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse;
import com.capstone.backend.domain.home.dto.response.TrendProductsResponse.Item;
import com.capstone.backend.domain.home.repository.ProductTrendDailyRepository;
import com.capstone.backend.domain.home.repository.TrendScoreSum;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 요즘 뜨는 제품. 제품별 하루 트렌드 지수를 BE 가 직접 모아 순위를 매긴다. 사용자와 무관한 전체 공통 순위다.
 *
 * AI 트렌드 API 는 가격과 증가율을 주지 않아 명세를 채울 수 없어 쓰지 않는다.
 * 순위는 최근 30일 지수 합이고, 관심 증가율은 직전 30일 합과 비교한다. 광고 여부나 언급한 사람은 내리지 않는다.
 */
@Service
@RequiredArgsConstructor
public class TrendService {

    /** 오늘을 포함해 거슬러 올라가는 날 수. 직전 기간도 같은 길이다 */
    static final int PERIOD_DAYS = 30;
    static final int MAX_LIMIT = 20;

    private final ProductTrendDailyRepository productTrendDailyRepository;
    private final ProductRepository productRepository;
    private final HwadamProperties hwadamProperties;

    /** 개수가 1~20 밖이면 VALIDATION_ERROR. 기록이 없으면 빈 목록이다 */
    @Transactional(readOnly = true)
    public TrendProductsResponse getProducts(int limit) {
        return getProducts(limit, LocalDate.now(hwadamProperties.getZone()));
    }

    TrendProductsResponse getProducts(int limit, LocalDate today) {
        if (limit < 1 || limit > MAX_LIMIT) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        LocalDate recentFrom = today.minusDays(PERIOD_DAYS - 1);
        LocalDate previousTo = recentFrom.minusDays(1);
        LocalDate previousFrom = previousTo.minusDays(PERIOD_DAYS - 1);

        List<TrendScoreSum> top = productTrendDailyRepository.findTopScoreSums(recentFrom, today, PageRequest.of(0, limit));
        List<UUID> productIds = top.stream().map(TrendScoreSum::productId).toList();
        Map<UUID, Double> previous = productIds.isEmpty() ? Map.of()
                : productTrendDailyRepository.findScoreSums(productIds, previousFrom, previousTo).stream()
                .collect(Collectors.toMap(TrendScoreSum::productId, TrendScoreSum::total, (a, b) -> a));
        Map<UUID, Product> products = productIds.isEmpty() ? Map.of()
                : productRepository.findAllById(productIds).stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));

        List<Item> items = new ArrayList<>();
        for (TrendScoreSum sum : top) {
            Product product = products.get(sum.productId());
            if (product == null) {
                // 상품이 지워져 보여 줄 정보가 없으면 순위에서 뺀다
                continue;
            }
            items.add(new Item(items.size() + 1, product.getId(), product.getName(), product.getBrand(),
                    product.getLowestPrice() != null ? product.getLowestPrice() : product.getOriginalPrice(),
                    product.getImageUrl(), changePercent(sum.total(), previous.get(sum.productId()))));
        }
        return new TrendProductsResponse(PERIOD_DAYS, items,
                productTrendDailyRepository.findLatestUpdatedAt(recentFrom, today));
    }

    /** (최근 합 − 직전 합) / 직전 합 × 100 을 반올림한다. 직전 합이 없거나 0 이하면 비교할 수 없어 null */
    static Integer changePercent(Double recent, Double previous) {
        if (recent == null || previous == null || previous <= 0) {
            return null;
        }
        return (int) Math.round((recent - previous) / previous * 100);
    }
}
