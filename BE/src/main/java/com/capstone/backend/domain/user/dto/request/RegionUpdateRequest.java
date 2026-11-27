package com.capstone.backend.domain.user.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

/** 생활 환경을 계산할 지역. 지역 코드는 시·도 이름(서울, 경기 등)이고 표시 이름은 화면에 보여 줄 이름이다 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
public class RegionUpdateRequest {

    @NotBlank(message = "regionCode는 필수입니다.")
    private String regionCode;

    @NotBlank(message = "regionName은 필수입니다.")
    @Size(max = 50, message = "regionName은 50자 이하여야 합니다.")
    private String regionName;
}
