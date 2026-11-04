package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse;
import com.capstone.backend.domain.recommendation.dto.response.BundleSlotOptionsResponse.Option;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Bundle;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultV2Response.Slot;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.service.BundleSnapshotReader.Candidate;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 예산 세트의 칸 교체 후보. 가격과 점수를 다시 더하는 계산이라 AI 를 거치지 않고 job 에 저장된 값으로 계산한다.
 *
 * 조합과 칸은 추천 결과 조회와 같은 변환으로 찾아, 화면이 받은 칸 키와 가격이 그대로 맞는다.
 * 칸별 후보가 없는 기존 결과는 칸이 없는 것으로 본다.
 */
@Service
@RequiredArgsConstructor
public class BundleOptionService {

    private final RecommendationRepository recommendationRepository;
    private final ProductRepository productRepository;
    private final JsonUtil jsonUtil;

    @Transactional(readOnly = true)
    public BundleSlotOptionsResponse getOptions(UUID userId, UUID jobId, int bundleIndex, String slotKey) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .filter(found -> found.getStatus() == JobStatus.COMPLETED)
                .orElseThrow(BundleOptionService::notFound);
        JsonNode result = readTree(job.getResult());

        Bundle bundle = bundleAt(result, bundleIndex);
        Slot slot = bundle.getSlots().stream()
                .filter(found -> slotKey.equals(found.getSlotKey()))
                .findFirst()
                .orElseThrow(BundleOptionService::notFound);
        List<Candidate> candidates = BundleSnapshotReader.find(readTree(job.getStateSnapshot()), slotKey)
                .orElseThrow(BundleOptionService::notFound)
                .candidates();

        Integer budget = ResultAssembler.intOrNull(result.path("query").path("budgetTotal"));
        return new BundleSlotOptionsResponse(budget, bundle.getTotal(), options(bundle.getTotal(), budget, slot, candidates));
    }

    private Bundle bundleAt(JsonNode result, int bundleIndex) {
        List<UUID> productIds = ResultAssembler.productIdsOf(result);
        Map<String, Product> products = productIds.isEmpty() ? Map.of()
                : productRepository.findAllById(productIds).stream()
                .collect(Collectors.toMap(product -> product.getId().toString(), Function.identity()));
        return ResultAssembler.bundles(result.path("bundles"), result.path("query"), products).stream()
                .filter(bundle -> bundle.getIndex() == bundleIndex)
                .findFirst()
                .orElseThrow(BundleOptionService::notFound);
    }

    /**
     * 지금 칸의 제품은 합계와 맞도록 칸의 가격으로 계산하고, 후보에 없으면 목록에 넣는다.
     * 점수가 없는 후보는 적합도순에 넣을 수 없어 빼지만, 지금 칸의 제품은 남긴다.
     */
    private static List<Option> options(int total, Integer budget, Slot slot, List<Candidate> candidates) {
        // 칸 가격을 모르면 합계에 들어 있지 않은 것으로 본다
        int currentPrice = slot.getPrice() == null ? 0 : slot.getPrice();
        int totalWithoutSlot = total - currentPrice;

        List<Option> options = new ArrayList<>();
        boolean currentListed = false;
        for (Candidate candidate : candidates) {
            boolean current = candidate.productId().equals(slot.getProductId());
            if (current) {
                currentListed = true;
                options.add(option(candidate.productId(), candidate.name(), currentPrice,
                        candidate.score() != null ? candidate.score() : slot.getScore(), totalWithoutSlot, budget, true));
            } else if (candidate.score() != null) {
                options.add(option(candidate.productId(), candidate.name(), candidate.price(), candidate.score(),
                        totalWithoutSlot, budget, false));
            }
        }
        if (!currentListed && slot.getProductId() != null) {
            options.add(option(slot.getProductId(), slot.getName(), currentPrice, slot.getScore(), totalWithoutSlot, budget, true));
        }
        options.sort(Comparator.comparing(Option::getScore, Comparator.nullsLast(Comparator.reverseOrder())));
        return options;
    }

    private static Option option(String productId, String name, int price, Integer score, int totalWithoutSlot,
                                 Integer budget, boolean current) {
        int newTotal = totalWithoutSlot + price;
        Integer remaining = budget == null ? null : budget - newTotal;
        boolean selectable = remaining == null || remaining >= 0;
        return new Option(productId, name, price, score, newTotal, remaining, current, selectable,
                selectable ? null : -remaining);
    }

    /** 깨진 결과에서는 조합과 칸을 찾을 수 없다 */
    private JsonNode readTree(String json) {
        try {
            return jsonUtil.readTree(json);
        } catch (BusinessException e) {
            throw notFound();
        }
    }

    private static BusinessException notFound() {
        return new BusinessException(ErrorCode.NOT_FOUND);
    }
}
