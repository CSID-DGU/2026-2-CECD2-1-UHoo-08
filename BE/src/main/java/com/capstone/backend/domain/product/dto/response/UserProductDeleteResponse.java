package com.capstone.backend.domain.product.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

@Getter
@AllArgsConstructor
public class UserProductDeleteResponse {
    /** 삭제한 보유 제품 ID */
    private UUID userProductId;
}
