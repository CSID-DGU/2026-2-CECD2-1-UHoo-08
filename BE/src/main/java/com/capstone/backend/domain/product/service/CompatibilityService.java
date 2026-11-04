package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityCheckResponse;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityPairDetail;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse.Pair;
import com.capstone.backend.domain.product.dto.response.ProductCompatibilityResponse.Schedule;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 이 제품을 지금 쓰는 제품들과 함께 써도 되는지 판정한다.
 *
 * 성분 정규화와 판정 규칙은 AI 에 있어 다시 구현하지 않고, AI 결과를 화면 모양으로 바꾼다.
 * AI 호출이 오래 걸릴 수 있어 DB 연결을 붙잡지 않도록 트랜잭션을 걸지 않는다.
 */
@Service
@RequiredArgsConstructor
public class CompatibilityService {

    private static final List<String> BASIS = List.of(
            "성분표에 적힌 성분끼리만 비교해요",
            "규칙 테이블 기반이라 같은 입력이면 항상 같은 결과가 나와요",
            "피부 반응은 사람마다 달라요. 참고로만 봐주세요");

    private final UserProductRepository userProductRepository;
    private final ProductRepository productRepository;
    private final AiInternalClient aiInternalClient;

    public ProductCompatibilityResponse check(UUID userId, UUID productId) {
        if (!productRepository.existsById(productId)) {
            throw new BusinessException(ErrorCode.PRODUCT_NOT_FOUND);
        }

        // 같은 제품끼리는 비교하지 않는다. 다른 제품을 쓰지 않으면 물어볼 것이 없다
        Map<String, UserProduct> others = userProductRepository
                .findByUserIdAndUsageTypeIn(userId, List.of(UsageType.USING)).stream()
                .filter(row -> !row.getProductId().equals(productId))
                .collect(Collectors.toMap(row -> row.getId().toString(), Function.identity()));
        if (others.isEmpty()) {
            return result(List.of());
        }

        Map<UUID, String> names = productRepository.findAllById(
                        others.values().stream().map(UserProduct::getProductId).distinct().toList()).stream()
                .collect(Collectors.toMap(Product::getId, Product::getName));

        // 걸러 낸 쌍으로 판정을 다시 정하므로 AI 의 level 은 쓰지 않는다
        CompatibilityCheckResponse checked = aiInternalClient.checkCompatibility(userId, productId);
        List<Pair> pairs = checked.pairs().stream()
                .filter(CompatibilityService::isConflict)
                .filter(pair -> others.containsKey(pair.userProductId()))
                .filter(pair -> names.containsKey(others.get(pair.userProductId()).getProductId()))
                .map(pair -> {
                    UserProduct row = others.get(pair.userProductId());
                    return toPair(pair, row.getId(), names.get(row.getProductId()));
                })
                .sorted(Comparator.comparing(Pair::getLevel))
                .toList();
        return result(pairs);
    }

    /** 괜찮은 쌍은 충돌이 아니다 */
    private static boolean isConflict(CompatibilityPairDetail pair) {
        return pair.level() == CompatibilityLevel.AVOID || pair.level() == CompatibilityLevel.SEPARATE;
    }

    private static ProductCompatibilityResponse result(List<Pair> pairs) {
        CompatibilityLevel level = pairs.isEmpty() ? CompatibilityLevel.OK : pairs.get(0).getLevel();
        return new ProductCompatibilityResponse(level, bannerText(level, pairs), pairs, BASIS);
    }

    /** N 은 이 단계로 걸린 보유 제품 수다. 한 제품에서 성분 쌍이 여럿 걸릴 수 있어 쌍을 세지 않는다 */
    private static String bannerText(CompatibilityLevel level, List<Pair> pairs) {
        long count = pairs.stream()
                .filter(pair -> pair.getLevel() == level)
                .map(Pair::getUserProductId)
                .distinct()
                .count();
        return switch (level) {
            case AVOID -> "지금 쓰시는 제품 " + count + "개와 같이 쓰면 안 돼요";
            case SEPARATE -> "지금 쓰시는 제품 " + count + "개와 시간대를 나눠 쓰세요";
            case OK -> null;
        };
    }

    private static Pair toPair(CompatibilityPairDetail pair, UUID userProductId, String userProductName) {
        return new Pair(userProductId, userProductName, pair.ingredientA(), pair.ingredientB(), pair.level(),
                title(pair), reason(pair), schedule(pair.schedule()));
    }

    private static String title(CompatibilityPairDetail pair) {
        String a = pair.ingredientA();
        String b = pair.ingredientB();
        return a + KoreanParticle.and(a) + " " + b + KoreanParticle.topic(b) + " "
                + (pair.level() == CompatibilityLevel.AVOID ? "같이 쓰지 마세요" : "시간대를 나눠 쓰세요");
    }

    private static String reason(CompatibilityPairDetail pair) {
        if (pair.advice() != null && !pair.advice().isBlank()) {
            return pair.advice();
        }
        return pair.level() == CompatibilityLevel.AVOID
                ? "성분 조합상 같이 쓰지 않는 것이 좋아요"
                : "성분 조합상 시간대를 나눠 쓰는 것이 좋아요";
    }

    /** AI 는 시간대 안내를 문구 하나로 준다. 아침, 저녁으로 나눌 수 없어 팁에 넣는다 */
    private static Schedule schedule(String text) {
        return text == null || text.isBlank() ? null : new Schedule(null, null, text);
    }
}
