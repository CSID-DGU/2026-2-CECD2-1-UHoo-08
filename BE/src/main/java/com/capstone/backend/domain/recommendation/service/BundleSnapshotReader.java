package com.capstone.backend.domain.recommendation.service;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * job 의 그래프 상태(state_snapshot)에서 예산 세트의 칸별 후보(bundle_slots)를 읽는다.
 *
 * 조합이 달라도 칸별 후보는 같아 job 에 한 벌만 있다. 블록이 없거나 모양이 잘못되면 후보가 없는 것으로 읽는다.
 * 칸 키가 없는 칸과, 제품 id 나 가격을 모르는 후보는 뺀다. 교체하면 합계를 다시 계산하므로 가격이 꼭 있어야 한다.
 */
public final class BundleSnapshotReader {

    private BundleSnapshotReader() {
    }

    public record BundleSlot(String slotKey, String label, List<Candidate> candidates) {
    }

    /** score 는 AI 가 주지 않으면 null */
    public record Candidate(String productId, String name, int price, Integer score) {
    }

    /**
     * @param stateSnapshot job 의 그래프 상태. 없으면 MissingNode
     */
    public static List<BundleSlot> slots(JsonNode stateSnapshot) {
        JsonNode array = stateSnapshot.path("bundle_slots");
        if (!array.isArray()) {
            return List.of();
        }
        List<BundleSlot> slots = new ArrayList<>();
        array.forEach(node -> {
            String slotKey = textOrNull(node.path("slotKey"));
            if (slotKey != null) {
                String label = textOrNull(node.path("label"));
                slots.add(new BundleSlot(slotKey, label != null ? label : slotKey, candidates(node.path("candidates"))));
            }
        });
        return slots;
    }

    public static Optional<BundleSlot> find(JsonNode stateSnapshot, String slotKey) {
        return slots(stateSnapshot).stream().filter(slot -> slot.slotKey().equals(slotKey)).findFirst();
    }

    private static List<Candidate> candidates(JsonNode array) {
        List<Candidate> candidates = new ArrayList<>();
        array.forEach(node -> {
            String productId = textOrNull(node.path("productId"));
            JsonNode price = node.path("price");
            if (productId != null && price.isIntegralNumber() && price.asInt() >= 0) {
                JsonNode score = node.path("score");
                candidates.add(new Candidate(productId, textOrNull(node.path("name")), price.asInt(),
                        score.isNumber() ? Integer.valueOf(score.asInt()) : null));
            }
        });
        return candidates;
    }

    private static String textOrNull(JsonNode node) {
        return node.isTextual() && !node.asText().isBlank() ? node.asText() : null;
    }
}
