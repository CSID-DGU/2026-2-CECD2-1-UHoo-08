package com.capstone.backend.domain.product.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

/** 제품명 사진 인식 결과. recognitionId 로 기한 사진 인식과 보유 제품 등록을 잇는다 */
@Getter
@AllArgsConstructor
public class PhotoRecognitionResponse {
    private UUID recognitionId;
    /** 사진에서 읽은 글자. 읽지 못했으면 빈 문자열 */
    private String readText;
    /** 일치도 높은 순, 최대 3개. 없으면 빈 배열 */
    private List<Candidate> candidates;

    @Getter
    @AllArgsConstructor
    public static class Candidate {
        private String productId;
        private String name;
        private String brand;
        /** 상품 테이블에 용량 정보가 없어 지금은 항상 null */
        private String volume;
        private String imageUrl;
        /** 일치도 0~100 */
        private int matchScore;
    }
}
