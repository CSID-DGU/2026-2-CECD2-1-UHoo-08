package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse.Conflict;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.inOrder;

@ExtendWith(MockitoExtension.class)
class UserProductRegistrationServiceTest {

    @Mock
    UserProductService userProductService;
    @Mock
    CompatibilityService compatibilityService;
    @InjectMocks
    UserProductRegistrationService service;

    @Test
    void 등록을_마친_뒤_궁합을_확인해_충돌을_함께_돌려준다() {
        UUID userId = UUID.randomUUID();
        UUID productId = UUID.randomUUID();
        UUID userProductId = UUID.randomUUID();
        UserProductCreateRequest request = UserProductCreateRequest.builder().productId(productId).build();
        Conflict conflict = new Conflict(UUID.randomUUID(), "레티놀 앰플", "AVOID", "같이 쓰지 마세요");
        given(userProductService.create(userId, request))
                .willReturn(new UserProductCreateResponse(userProductId, productId, "세럼", List.of()));
        given(compatibilityService.conflictsOf(userId, productId)).willReturn(List.of(conflict));

        UserProductCreateResponse response = service.create(userId, request);

        assertThat(response.getUserProductId()).isEqualTo(userProductId);
        assertThat(response.getProductId()).isEqualTo(productId);
        assertThat(response.getName()).isEqualTo("세럼");
        assertThat(response.getConflicts()).containsExactly(conflict);
        InOrder order = inOrder(userProductService, compatibilityService);
        order.verify(userProductService).create(userId, request);
        order.verify(compatibilityService).conflictsOf(userId, productId);
    }
}
