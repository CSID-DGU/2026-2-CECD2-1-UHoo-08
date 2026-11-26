package com.capstone.backend.domain.home.batch;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.HomeRunRequest;
import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.UUID;

/**
 * 하루 한 번 홈 카드(루틴 점검, 환경 기반 추천) 생성을 AI 에 요청한다.
 *
 * AI 는 실패하면 기존 카드를 덮어쓰지 않으므로, 실패한 사용자는 카드가 오래된 채로 남아 다음 날 앞쪽에서 다시 요청된다.
 * 트랜잭션을 걸지 않는다. 호출 사이에 기다리는 동안 DB 커넥션을 잡고 있게 된다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class HomeRecommendationScheduler {

    static final int ROUTINE_MIN_OWNED = 2;
    static final int ENV_MIN_OWNED = 1;

    private final HomeRecommendationRepository homeRecommendationRepository;
    private final AiInternalClient aiInternalClient;
    private final HwadamProperties hwadamProperties;

    /** 종류별로 조회하고 요청한다. 한 종류의 조회가 실패해도 다른 종류의 요청은 나간다 */
    @Scheduled(cron = "${hwadam.batch.home-cron}", zone = "${hwadam.batch.zone}")
    public void requestCards() {
        if (requestCards(HomeRecommendationKind.ROUTINE, ROUTINE_MIN_OWNED, false)) {
            requestCards(HomeRecommendationKind.ENV, ENV_MIN_OWNED, true);
        }
    }

    /** @return 기다리는 중 중단되면 false. 이때는 다음 종류도 요청하지 않는다 */
    private boolean requestCards(HomeRecommendationKind kind, int minOwned, boolean regionRequired) {
        List<UUID> targets;
        try {
            targets = homeRecommendationRepository.findCardTargets(kind, minOwned, regionRequired,
                    hwadamProperties.getBatch().isHomeIncludeSynthetic());
        } catch (RuntimeException e) {
            log.error("[HomeRecommendation] 대상 조회 실패: kind={}, error={}", kind, e.getMessage());
            return true;
        }

        int notSent = 0;
        for (int i = 0; i < targets.size(); i++) {
            UUID userId = targets.get(i);
            try {
                aiInternalClient.runHome(new HomeRunRequest(userId.toString(), kind.name()));
            } catch (RuntimeException e) {
                notSent++;
                log.warn("[HomeRecommendation] AI 호출 실패: userId={}, kind={}, error={}", userId, kind, e.getMessage());
            }
            if (!waitForNextCall()) {
                log.warn("[HomeRecommendation] 기다리는 중 중단되어 {} 대상 {}건 중 {}건만 요청함", kind, targets.size(), i + 1);
                return false;
            }
        }
        // 호출은 보내고 바로 돌아오므로, 보낸 뒤의 실패는 여기서 셀 수 없고 AiInternalClient 가 건마다 오류 로그로 남긴다
        log.info("[HomeRecommendation] {} 카드 생성 요청 {}건 중 보내지 못한 요청 {}건", kind, targets.size(), notSent);
        return true;
    }

    /** 호출 간격. 버리면 설정한 속도를 넘으므로 올린다. 그래서 초당 1000회가 넘는 설정은 초당 1000회로 돈다 */
    static long callGapMillis(int callsPerSecond) {
        return (1000L + callsPerSecond - 1) / callsPerSecond;
    }

    /** 초당 호출 수에 맞춰 기다린다. 중단되면 false */
    boolean waitForNextCall() {
        try {
            Thread.sleep(callGapMillis(hwadamProperties.getBatch().getHomeCallsPerSecond()));
            return true;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
}
