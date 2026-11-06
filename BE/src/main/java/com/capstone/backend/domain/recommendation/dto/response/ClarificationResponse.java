package com.capstone.backend.domain.recommendation.dto.response;

import com.capstone.backend.domain.recommendation.enums.JobStatus;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

/** 추가 질문 답변 접수 결과. 같은 job 이 이어서 진행되므로 다시 상태를 폴링한다 */
@Getter
@AllArgsConstructor
public class ClarificationResponse {
    private UUID jobId;
    private JobStatus status;
}
