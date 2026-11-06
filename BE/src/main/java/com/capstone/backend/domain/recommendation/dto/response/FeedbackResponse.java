package com.capstone.backend.domain.recommendation.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

/** 피드백 등록 결과 */
@Getter
@AllArgsConstructor
public class FeedbackResponse {
    private String feedbackId;
    /** 토스트로 보여 줄 안내 문구 */
    private String message;
    /** 가중치가 바뀌었으면 되돌리기용 ID. 가중치는 AI 가 비동기로 반영해 항상 null */
    private UUID changeId;
}
