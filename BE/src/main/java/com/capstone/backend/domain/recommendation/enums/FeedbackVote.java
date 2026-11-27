package com.capstone.backend.domain.recommendation.enums;

/**
 * recommendation_feedback.vote. 추천 결과의 제품 하나에 대한 반응.
 * 등록 뒤 토스트로 보여 줄 안내 문구를 가진다. 별로예요는 이유와 상관없이 같은 문구다.
 */
public enum FeedbackVote {

    UP("좋아하신 점을 다음 추천에도 반영할게요"),
    DOWN("의견을 다음 추천에 반영할게요");

    private final String message;

    FeedbackVote(String message) {
        this.message = message;
    }

    public String message() {
        return message;
    }
}
