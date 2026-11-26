package com.capstone.backend.domain.home.repository;

import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.function.Predicate;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 홈 카드 대상 쿼리를 실제 DB 에서 돌려, 사용자를 하나씩 따져 본 결과와 비교한다. 읽기만 한다.
 * 쿼리를 돌릴 테스트 DB 가 없어 접속 주소가 없는 CI 에서는 건너뛴다.
 */
@SpringBootTest
@EnabledIfEnvironmentVariable(named = "SPRING_DATASOURCE_URL", matches = ".+")
class HomeCardTargetQueryTest {

    @Autowired
    HomeRecommendationRepository homeRecommendationRepository;
    @Autowired
    UserRepository userRepository;
    @Autowired
    UserProductRepository userProductRepository;

    private int owned(User user) {
        return userProductRepository.findIdsByUserIdAndUsageType(user.getId(), UsageType.USING).size();
    }

    private Set<UUID> expected(Predicate<User> rule) {
        return userRepository.findAll().stream().filter(rule).map(User::getId).collect(Collectors.toSet());
    }

    private static boolean hasRegion(User user) {
        return user.getRegion() != null && !user.getRegion().isBlank();
    }

    @Test
    void 루틴_대상은_보유_제품이_2개_이상인_사용자다() {
        List<UUID> targets = homeRecommendationRepository.findCardTargets(HomeRecommendationKind.ROUTINE, 2, false, true);

        assertThat(targets).doesNotHaveDuplicates();
        assertThat(Set.copyOf(targets)).isEqualTo(expected(user -> owned(user) >= 2));
    }

    @Test
    void 환경_대상은_지역이_있고_보유_제품이_1개_이상인_사용자다() {
        List<UUID> targets = homeRecommendationRepository.findCardTargets(HomeRecommendationKind.ENV, 1, true, true);

        assertThat(targets).doesNotHaveDuplicates();
        assertThat(Set.copyOf(targets)).isEqualTo(expected(user -> hasRegion(user) && owned(user) >= 1));
    }

    @Test
    void 합성_사용자는_설정에_따라_뺀다() {
        List<UUID> targets = homeRecommendationRepository.findCardTargets(HomeRecommendationKind.ROUTINE, 0, false, false);

        assertThat(Set.copyOf(targets)).isEqualTo(expected(user -> !user.isSynthetic()));
    }
}
