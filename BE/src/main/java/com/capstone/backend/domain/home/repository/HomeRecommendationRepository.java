package com.capstone.backend.domain.home.repository;

import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface HomeRecommendationRepository extends JpaRepository<HomeRecommendation, HomeRecommendation.Key> {

    /**
     * 이 카드를 만들 사용자. 카드가 없는 사용자, 카드가 오래된 사용자 순서다.
     *
     * @param minOwned 쓰는 중인 보유 제품의 최소 개수
     */
    @Query("""
            SELECT u.id FROM User u
            LEFT JOIN HomeRecommendation h ON h.userId = u.id AND h.kind = :kind
            WHERE (:includeSynthetic = true OR u.isSynthetic = false)
              AND (:regionRequired = false OR (u.region IS NOT NULL AND TRIM(u.region) <> ''))
              AND (SELECT COUNT(up) FROM UserProduct up
                   WHERE up.userId = u.id
                     AND up.usageType = com.capstone.backend.domain.product.enums.UsageType.USING) >= :minOwned
            ORDER BY h.generatedAt ASC NULLS FIRST, u.id ASC
            """)
    List<UUID> findCardTargets(@Param("kind") HomeRecommendationKind kind,
                               @Param("minOwned") long minOwned,
                               @Param("regionRequired") boolean regionRequired,
                               @Param("includeSynthetic") boolean includeSynthetic);
}
