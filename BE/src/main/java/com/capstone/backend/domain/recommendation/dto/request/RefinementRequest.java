package com.capstone.backend.domain.recommendation.dto.request;

import com.capstone.backend.domain.recommendation.enums.RefinePreset;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.AssertTrue;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

/** 조건 추가(재탐색). 고른 조건과 직접 쓴 조건 중 하나는 있어야 한다. 목록에 없는 조건 키는 요청 오류다 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RefinementRequest {

    private List<RefinePreset> presetKeys;

    private String freeText;

    @JsonIgnore
    @AssertTrue(message = "presetKeys와 freeText 중 하나는 있어야 합니다.")
    public boolean isAnyGiven() {
        return (presetKeys != null && presetKeys.stream().anyMatch(key -> key != null))
                || (freeText != null && !freeText.isBlank());
    }
}
