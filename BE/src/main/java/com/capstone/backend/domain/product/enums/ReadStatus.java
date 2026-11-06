package com.capstone.backend.domain.product.enums;

/**
 * 사진에서 값을 읽었는지. 읽지 못한 값은 추측해서 채우지 않고 NOT_READ 로 두어 사용자가 직접 넣게 한다.
 */
public enum ReadStatus {

    READ,
    NOT_READ
}
