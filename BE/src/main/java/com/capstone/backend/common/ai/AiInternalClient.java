package com.capstone.backend.common.ai;

import com.capstone.backend.common.ai.dto.AiInternalDtos.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * AI 내부 API 호출.
 *
 * 경로와 요청 모양을 한 곳에 모은다. 기존 {@code AgentClient} 는
 * {@code Map<String, Object>} 로 본문을 만들어서, 필드 이름이 틀려도 컴파일이
 * 되고 런타임에 조용히 무시됐다.
 *
 * 호출은 두 갈래다.
 *   비동기 — 202 만 받고 끝낸다. 결과는 DB 로 온다. 응답을 기다리면
 *       추천 한 번에 수십 초를 붙잡고 있게 된다.
 *   동기 — 화면이 바로 기다리는 호출이다. 타임아웃을 짧게 둔다.
 *
 * AI 쪽이 아직 stub 이면 응답의 {@code stub} 이 true 로 온다. 비동기 호출은
 * 결과가 오지 않으므로, job 완료를 기다리는 화면은 그동안 진행 중으로 남는다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiInternalClient {

    private static final Duration SYNC_TIMEOUT = Duration.ofSeconds(30);
    /** 사진 두 장을 읽는 호출이라 조금 더 준다. */
    private static final Duration RECOGNIZE_TIMEOUT = Duration.ofSeconds(60);

    private final WebClient webClient;

    @Value("${ai.server-url}")
    private String aiServerUrl;

    // ── 비동기 ────────────────────────────────────────────────

    public void runAgentV2(AgentRunV2Request request) {
        postAsync("/internal/agent/run/v2", request);
    }

    public void clarify(AgentClarifyRequest request) {
        postAsync("/internal/agent/clarify", request);
    }

    public void runHome(HomeRunRequest request) {
        postAsync("/internal/home/run", request);
    }

    public void applyFeedback(FeedbackApplyRequest request) {
        postAsync("/internal/feedback/apply", request);
    }

    // ── 동기 ──────────────────────────────────────────────────

    public RecognizePhotosResponse recognizePhotos(RecognizePhotosRequest request) {
        return postSync("/internal/products/recognize-photos", request,
                RecognizePhotosResponse.class, RECOGNIZE_TIMEOUT);
    }

    public BundleSwapResponse swapBundleItem(BundleSwapRequest request) {
        return postSync("/internal/bundle/swap", request,
                BundleSwapResponse.class, SYNC_TIMEOUT);
    }

    public TrendsResponse getTrends(int limit) {
        return webClient.get()
                .uri(aiServerUrl + "/internal/trends?limit=" + limit)
                .retrieve()
                .bodyToMono(TrendsResponse.class)
                .timeout(SYNC_TIMEOUT)
                .block();
    }

    // ── 공통 ──────────────────────────────────────────────────

    /**
     * 던지고 잊는다. 실패해도 예외를 올리지 않고 로그만 남긴다.
     *
     * 호출한 쪽은 이미 job 을 PENDING 으로 만들어 두었다. 여기서 예외를
     * 올리면 사용자 요청이 실패로 끝나지만, AI 는 그 사이 실행을 시작했을 수도
     * 있어 상태가 엇갈린다. 실패는 job 이 진행되지 않는 것으로 드러난다.
     */
    private void postAsync(String path, Object body) {
        webClient.post()
                .uri(aiServerUrl + path)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(Accepted.class)
                .subscribe(
                        accepted -> {
                            if (accepted != null && accepted.stub()) {
                                log.warn("AI {} 는 아직 stub 이다. 결과가 오지 않는다.", path);
                            }
                        },
                        error -> log.error("AI {} 호출 실패: {}", path, error.getMessage())
                );
    }

    private <T> T postSync(String path, Object body, Class<T> responseType, Duration timeout) {
        return webClient.post()
                .uri(aiServerUrl + path)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(responseType)
                .timeout(timeout)
                .block();
    }
}
