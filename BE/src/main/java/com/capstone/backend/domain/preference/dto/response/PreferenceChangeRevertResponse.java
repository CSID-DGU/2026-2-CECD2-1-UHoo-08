package com.capstone.backend.domain.preference.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

/** 가중치 변경 되돌리기 결과 */
@Getter
@AllArgsConstructor
public class PreferenceChangeRevertResponse {
    private UUID changeId;
    private boolean reverted;
}
