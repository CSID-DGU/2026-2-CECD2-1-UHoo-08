package com.capstone.backend.domain.home.repository;

import com.capstone.backend.domain.home.entity.ProductTrendDaily;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.UUID;

public interface ProductTrendDailyRepository extends JpaRepository<ProductTrendDaily, ProductTrendDaily.Key> {

    /**
     * from ~ to(양끝 포함) 트렌드 지수 합이 0보다 큰 제품을 합 내림차순으로. 합이 같으면 제품 id 순으로 순서를 고정한다.
     * 지수가 비어 있는 날은 합에서 빠진다.
     */
    @Query("""
            SELECT new com.capstone.backend.domain.home.repository.TrendScoreSum(t.productId, SUM(t.trendScore))
            FROM ProductTrendDaily t
            WHERE t.date BETWEEN :from AND :to
            GROUP BY t.productId
            HAVING SUM(t.trendScore) > 0
            ORDER BY SUM(t.trendScore) DESC, t.productId
            """)
    List<TrendScoreSum> findTopScoreSums(@Param("from") LocalDate from, @Param("to") LocalDate to, Pageable pageable);

    /** 주어진 제품들의 from ~ to(양끝 포함) 트렌드 지수 합. 기록이 없는 제품은 결과에 없다 */
    @Query("""
            SELECT new com.capstone.backend.domain.home.repository.TrendScoreSum(t.productId, SUM(t.trendScore))
            FROM ProductTrendDaily t
            WHERE t.productId IN :productIds AND t.date BETWEEN :from AND :to
            GROUP BY t.productId
            """)
    List<TrendScoreSum> findScoreSums(@Param("productIds") Collection<UUID> productIds,
                                      @Param("from") LocalDate from, @Param("to") LocalDate to);

    /** from ~ to(양끝 포함) 기록이 마지막으로 갱신된 시각. 기록이 없으면 null */
    @Query("SELECT MAX(t.updatedAt) FROM ProductTrendDaily t WHERE t.date BETWEEN :from AND :to")
    OffsetDateTime findLatestUpdatedAt(@Param("from") LocalDate from, @Param("to") LocalDate to);
}
