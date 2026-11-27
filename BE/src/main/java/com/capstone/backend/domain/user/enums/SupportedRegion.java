package com.capstone.backend.domain.user.enums;

import java.util.Arrays;
import java.util.Optional;

/**
 * 환경 데이터를 볼 수 있는 지역. users.region 과 env_daily.region 에 들어가는 시·도 이름이다.
 *
 * AI 환경 수집(services/iot/weather.py)의 REGIONS 키와 같은 목록이어야 한다.
 * AI 는 모르는 지역을 받으면 기본 지역으로 바꿔 버리므로, 목록에 없는 값은 BE 에서 막는다.
 * 광주와 전남은 AI 에서 한 지역(전남광주)으로 다룬다.
 */
public enum SupportedRegion {

    SEOUL("서울"),
    BUSAN("부산"),
    DAEGU("대구"),
    INCHEON("인천"),
    DAEJEON("대전"),
    ULSAN("울산"),
    SEJONG("세종"),
    GYEONGGI("경기"),
    GANGWON("강원"),
    CHUNGBUK("충북"),
    CHUNGNAM("충남"),
    JEONBUK("전북"),
    JEONNAM_GWANGJU("전남광주"),
    GYEONGBUK("경북"),
    GYEONGNAM("경남"),
    JEJU("제주");

    private final String regionName;

    SupportedRegion(String regionName) {
        this.regionName = regionName;
    }

    /** 저장하고 환경 데이터를 찾을 때 쓰는 시·도 이름 */
    public String regionName() {
        return regionName;
    }

    /** 시·도 이름으로 찾는다. 지원하지 않는 지역이면 비어 있다 */
    public static Optional<SupportedRegion> fromName(String name) {
        return Arrays.stream(values()).filter(region -> region.regionName.equals(name)).findFirst();
    }
}
