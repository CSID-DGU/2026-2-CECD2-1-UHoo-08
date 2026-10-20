package com.capstone.backend.domain.product.dto.response;

import com.capstone.backend.domain.product.enums.ReadStatus;
import lombok.AllArgsConstructor;
import lombok.Getter;

/** 기한 사진 인식 결과. 읽지 못한 항목은 value=null, status=NOT_READ */
@Getter
@AllArgsConstructor
public class ExpiryRecognitionResponse {
    /** 유통기한 YYYY-MM-DD */
    private ReadValue<String> expiryDate;
    /** 개봉 후 사용 기간(개월) */
    private ReadValue<Integer> paoMonths;
    /** 제조일 YYYY-MM-DD */
    private ReadValue<String> manufacturedAt;

    @Getter
    @AllArgsConstructor
    public static class ReadValue<T> {
        private T value;
        private ReadStatus status;

        /** 값이 있으면 READ, null 이면 NOT_READ */
        public static <T> ReadValue<T> of(T value) {
            return new ReadValue<>(value, value == null ? ReadStatus.NOT_READ : ReadStatus.READ);
        }
    }
}
