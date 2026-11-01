package com.capstone.backend.domain.home.enums;

/**
 * 환경 일별 추이에서 볼 수 있는 지표. 그래프 위에 보여 줄 이름을 가진다.
 * 지표별로 어느 값을 읽고 어떤 기준으로 초과를 판정할지는 환경 서비스가 정한다.
 */
public enum EnvMetric {

    /** 하루 최고 자외선 지수 */
    UV("자외선 지수"),
    /** 하루 평균 PM10 */
    PM("미세먼지"),
    /** 하루 평균 습도 */
    HUMIDITY("습도"),
    /** 하루 평균 기온 */
    TEMP("기온");

    private final String label;

    EnvMetric(String label) {
        this.label = label;
    }

    public String label() {
        return label;
    }
}
