package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.Pair;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse.UserProductRef;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.capstone.backend.domain.product.dto.response.UserProductListResponse.ConflictSummary;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 루틴 점검 결과에서 보유 제품 목록의 충돌 표시를 만든다.
 *
 * avoidCount 는 루틴 점검 화면과 같은 개수를 쓴다. 쌍 목록은 일부만 실릴 수 있어 쌍으로 세지 않는다.
 * 이름이 없는 상대는 문장을 만들 수 없어 건너뛴다.
 */
final class ProductConflicts {

    private final Map<UUID, String> texts;
    private final ConflictSummary summary;

    private ProductConflicts(Map<UUID, String> texts, ConflictSummary summary) {
        this.texts = texts;
        this.summary = summary;
    }

    static ProductConflicts none() {
        return new ProductConflicts(Map.of(), ConflictSummary.none());
    }

    static ProductConflicts from(RoutineCheckResponse check) {
        List<Pair> avoidPairs = check.getPairs().stream()
                .filter(pair -> pair.getLevel() == CompatibilityLevel.AVOID)
                .toList();
        return new ProductConflicts(textsOf(avoidPairs),
                new ConflictSummary(check.getCounts().getAvoid(), summaryText(avoidPairs, check.getCounts().getAvoid())));
    }

    /** 이 제품의 충돌 한 줄. 충돌이 없으면 null */
    String textOf(UUID userProductId) {
        return texts.get(userProductId);
    }

    ConflictSummary summary() {
        return summary;
    }

    private static Map<UUID, String> textsOf(List<Pair> avoidPairs) {
        Map<UUID, Set<String>> partners = new LinkedHashMap<>();
        avoidPairs.forEach(pair -> {
            addPartner(partners, pair.getA(), pair.getB());
            addPartner(partners, pair.getB(), pair.getA());
        });
        Map<UUID, String> texts = new HashMap<>();
        partners.forEach((id, names) -> texts.put(id, sentence(names)));
        return texts;
    }

    private static void addPartner(Map<UUID, Set<String>> partners, UserProductRef self, UserProductRef partner) {
        if (hasName(partner)) {
            partners.computeIfAbsent(UUID.fromString(self.getUserProductId()), id -> new LinkedHashSet<>())
                    .add(partner.getName());
        }
    }

    private static String sentence(Set<String> names) {
        String joined = String.join(", ", names);
        return joined + KoreanParticle.and(joined) + " 같이 쓰지 마세요";
    }

    /** 첫 쌍을 문구로 쓰고, 개수가 더 많으면 나머지를 외 N건으로 붙인다 */
    private static String summaryText(List<Pair> avoidPairs, int avoidCount) {
        if (avoidCount <= 0) {
            return null;
        }
        return avoidPairs.stream()
                .filter(pair -> hasName(pair.getA()) && hasName(pair.getB()))
                .findFirst()
                .map(pair -> pair.getA().getName() + " × " + pair.getB().getName()
                        + (avoidCount > 1 ? " 외 " + (avoidCount - 1) + "건" : ""))
                .orElse(null);
    }

    private static boolean hasName(UserProductRef ref) {
        return ref.getName() != null && !ref.getName().isBlank();
    }
}
