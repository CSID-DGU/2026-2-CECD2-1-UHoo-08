package com.capstone.backend.domain.user.dto.response;

import com.capstone.backend.domain.user.entity.User;
import lombok.AllArgsConstructor;
import lombok.Getter;

/** 저장된 사용자 지역 */
@Getter
@AllArgsConstructor
public class RegionResponse {

    /** 시·도 이름. 환경 데이터를 찾는 키다 */
    private String regionCode;
    /** 화면에 보여 줄 지역 이름 */
    private String regionName;

    public static RegionResponse from(User user) {
        return new RegionResponse(user.getRegion(), user.getRegionLabel());
    }
}
