package com.capstone.backend.domain.product.dto.response;

import com.capstone.backend.domain.product.enums.UserProductStatus;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.UUID;

@Getter
@AllArgsConstructor
public class UserProductUpdateResponse {
    private UUID userProductId;
    private UserProductStatus status;
    private Integer remainingPct;
}
