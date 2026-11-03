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

import java.util.ArrayList;
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

    private record Target(UUID userId, HomeRecommendationKind kind) {
    }

    @Scheduled(cron = "${hwadam.batch.home-cron}", zone = "${hwadam.batch.zone}")
    public void requestCards() {
        List<Target> targets = targets();
        int failed = 0;
        for (int i = 0; i < targets.size(); i++) {
            if (i > 0 && !waitForNextCall()) {
                log.warn("[HomeRecommendation] 기다리는 중 중단되어 {}건 중 {}건만 요청함", targets.size(), i);
                return;
            }
            Target target = targets.get(i);
            try {
                aiInternalClient.runHome(new HomeRunRequest(target.userId().toString(), target.kind().name()));
            } catch (RuntimeException e) {
                failed++;
                log.warn("[HomeRecommendation] AI 호출 실패: userId={}, kind={}, error={}",
                        target.userId(), target.kind(), e.getMessage());
            }
        }
        log.info("[HomeRecommendation] 홈 카드 생성 요청 {}건, 실패 {}건", targets.size(), failed);
    }

    private List<Target> targets() {
        boolean includeSynthetic = hwadamProperties.getBatch().isHomeIncludeSynthetic();
        List<Target> targets = new ArrayList<>();
        homeRecommendationRepository
                .findCardTargets(HomeRecommendationKind.ROUTINE, ROUTINE_MIN_OWNED, false, includeSynthetic)
                .forEach(userId -> targets.add(new Target(userId, HomeRecommendationKind.ROUTINE)));
        homeRecommendationRepository
                .findCardTargets(HomeRecommendationKind.ENV, ENV_MIN_OWNED, true, includeSynthetic)
                .forEach(userId -> targets.add(new Target(userId, HomeRecommendationKind.ENV)));
        return targets;
    }

    /** 초당 호출 수에 맞춰 기다린다. 중단되면 false */
    boolean waitForNextCall() {
        try {
            Thread.sleep(1000L / hwadamProperties.getBatch().getHomeCallsPerSecond());
            return true;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
}
