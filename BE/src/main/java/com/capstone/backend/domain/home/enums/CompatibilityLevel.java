package com.capstone.backend.domain.home.enums;

/**
 * 보유 제품 두 개를 함께 쓸 때의 성분 궁합. 선언 순서가 루틴 점검 화면의 쌍 정렬 순서다.
 */
public enum CompatibilityLevel {

    /** 같이 쓰지 말 것 */
    AVOID,
    /** 시간을 나눠 쓸 것 */
    SEPARATE,
    /** 같이 써도 괜찮음 */
    OK
}
