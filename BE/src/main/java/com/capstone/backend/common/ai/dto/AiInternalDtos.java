package com.capstone.backend.common.ai.dto;

import java.util.List;
import java.util.Map;

/**
 * AI 내부 API 와 주고받는 값.
 *
 * AI 쪽 {@code AI/contracts/internal_api.py} 와 같은 모양이다. 한쪽만 고치면
 * 필드가 조용히 빠지고, 빠진 자리는 기본값으로 채워져 정상처럼 보인다.
 * 필드를 바꿀 때는 두 파일과 {@code docs/internal-api.md} 를 같이 고친다.
 *
 * 한 파일에 모아 둔 이유는 이 값들이 따로 쓰이지 않고 항상 이 계약 하나로
 * 함께 움직이기 때문이다. 파일이 열두 개로 흩어지면 계약이 바뀔 때 무엇을
 * 같이 고쳐야 하는지 보이지 않는다.
 */
public final class AiInternalDtos {

    private AiInternalDtos() {
    }

    /**
     * 비동기 엔드포인트의 응답.
     *
     * @param stub 아직 내용이 없는 경로다. true 면 결과가 오지 않으므로
     *             job 이 완료되기를 기다리면 안 된다.
     */
    public record Accepted(boolean accepted, String jobId, boolean stub) {
    }

    /** 추천 실행. 결과는 응답이 아니라 recommendation_jobs 로 온다. */
    public record AgentRunV2Request(
            String jobId,
            String userId,
            String rawQuery,
            /* SELF | POPULAR | OTHER */
            String basis,
            /* basis 가 OTHER 일 때 화면에서 입력한 다른 사람의 조건 */
            Map<String, Object> targetProfile,
            /* 조건 수정이면 직전 job */
            String parentJobId
    ) {
    }

    /** 되묻기에 대한 사용자의 답. 멈춰 있던 job 을 이어서 돌린다. */
    public record AgentClarifyRequest(String jobId, String answer) {
    }

    /** 사진 두 장. 제품명 면은 필수, 기한 면은 선택이다. */
    public record RecognizePhotosRequest(String nameImage, String dateImage) {
    }

    public record ProductCandidate(
            String productId,
            String name,
            String brand,
            String imageUrl,
            double confidence
    ) {
    }

    /**
     * 인식 결과. 읽지 못한 값은 null 로 온다.
     *
     * 비어 있다고 채워 넣지 않는다. 사용자가 확인하지 않고 넘긴 잘못된 기한은
     * 그대로 소진 알림이 된다.
     */
    public record RecognizePhotosResponse(
            List<ProductCandidate> candidates,
            String expiryDate,
            Integer paoMonths,
            String mfgDate,
            /* 인식 원본. user_products.recognized_raw 에 그대로 저장한다. */
            Map<String, Object> raw,
            boolean stub
    ) {
    }

    /** 홈 카드 생성. kind 는 ROUTINE | ENV. */
    public record HomeRunRequest(String userId, String kind) {
    }

    public record BundleSwapRequest(String jobId, int bundleIndex, int slot, String productId) {
    }

    /** bundle 은 추천 결과의 BundleOption 모양이다. */
    public record BundleSwapResponse(Map<String, Object> bundle, boolean stub) {
    }

    public record TrendItem(
            String productId,
            String name,
            String brand,
            String imageUrl,
            double trendScore,
            int mentionCount
    ) {
    }

    public record TrendsResponse(List<TrendItem> items, boolean stub) {
    }

    /** 이 사용자의 가중치 prior 재계산. 피드백 저장 뒤 한 번 던진다. */
    public record FeedbackApplyRequest(String userId) {
    }
}
