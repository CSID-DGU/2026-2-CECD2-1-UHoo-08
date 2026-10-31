package com.capstone.backend.domain.recommendation.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

/** 조건 추가 접수 결과. 새 job 으로 상태를 폴링한다 */
@Getter
@AllArgsConstructor
public class RefinementResponse {
    /** 새 job */
    private UUID jobId;
    /** 직전 job */
    private UUID parentJobId;
    private int estimatedSeconds;
}
