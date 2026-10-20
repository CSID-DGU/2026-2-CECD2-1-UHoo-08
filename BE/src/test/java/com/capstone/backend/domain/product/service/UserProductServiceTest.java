package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.RegistrationSource;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.util.ReflectionTestUtils;

import java.sql.SQLException;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class UserProductServiceTest {

    @Mock
    UserProductRepository userProductRepository;
    @Mock
    ProductRepository productRepository;
    @Mock
    PhotoRecognitionService photoRecognitionService;
    @InjectMocks
    UserProductService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();
    private final UUID userProductId = UUID.randomUUID();

    private void givenProduct() {
        Product product = Product.builder().id(productId).name("그린티 씨드 세럼").brand("이니스프리").category("skincare").build();
        given(productRepository.findById(productId)).willReturn(Optional.of(product));
    }

    private void givenNotUsing() {
        given(userProductRepository.existsByUserIdAndProductIdAndUsageType(userId, productId, UsageType.USING))
                .willReturn(false);
    }

    private ArgumentCaptor<UserProduct> givenSave() {
        ArgumentCaptor<UserProduct> captor = ArgumentCaptor.forClass(UserProduct.class);
        given(userProductRepository.saveAndFlush(captor.capture())).willAnswer(inv -> {
            UserProduct saved = inv.getArgument(0);
            ReflectionTestUtils.setField(saved, "id", userProductId);
            return saved;
        });
        return captor;
    }

    private UserProductCreateRequest.UserProductCreateRequestBuilder request() {
        return UserProductCreateRequest.builder().productId(productId).remainingPct(70).source(RegistrationSource.MANUAL);
    }

    @Test
    void 쓰는_중인_새_행으로_등록하고_빈_충돌_목록을_돌려준다() {
        givenProduct();
        givenNotUsing();
        ArgumentCaptor<UserProduct> saved = givenSave();

        UserProductCreateResponse response = service.create(userId, request()
                .openedAt(LocalDate.of(2026, 9, 20))
                .expiryDate(LocalDate.of(2027, 4, 18))
                .paoMonths(12)
                .build());

        assertThat(response.getUserProductId()).isEqualTo(userProductId);
        assertThat(response.getProductId()).isEqualTo(productId);
        assertThat(response.getName()).isEqualTo("그린티 씨드 세럼");
        assertThat(response.getConflicts()).isEmpty();

        UserProduct row = saved.getValue();
        assertThat(row.getUserId()).isEqualTo(userId);
        assertThat(row.getUsageType()).isEqualTo(UsageType.USING);
        assertThat(row.getOpenedAt()).isEqualTo(LocalDate.of(2026, 9, 20));
        assertThat(row.getExpiryDate()).isEqualTo(LocalDate.of(2027, 4, 18));
        assertThat(row.getPaoMonths()).isEqualTo(12);
        assertThat(row.getRemainingPct()).isEqualTo(70);
        assertThat(row.getSource()).isEqualTo(RegistrationSource.MANUAL);
        assertThat(row.getRecognizedRaw()).isNull();
        assertThat(row.getCreatedAt()).isNotNull();
        assertThat(row.getUpdatedAt()).isNotNull();
        verifyNoInteractions(photoRecognitionService);
    }

    @Test
    void 개봉일이_없으면_오늘로_둔다() {
        givenProduct();
        givenNotUsing();
        ArgumentCaptor<UserProduct> saved = givenSave();

        service.create(userId, request().build());

        assertThat(saved.getValue().getOpenedAt()).isEqualTo(LocalDate.now());
    }

    @Test
    void 사진_인식_결과로_등록하면_인식_원본을_옮기고_사진_경로로_둔다() {
        givenProduct();
        givenNotUsing();
        ArgumentCaptor<UserProduct> saved = givenSave();
        UUID recognitionId = UUID.randomUUID();
        PhotoRecognition recognition = PhotoRecognition.builder()
                .userId(userId).nameImageUrl("https://s/a.jpg")
                .raw("{\"readText\":\"GREEN TEA\"}")
                .expiresAt(OffsetDateTime.now().plusMinutes(10)).build();
        given(photoRecognitionService.getUsable(userId, recognitionId)).willReturn(recognition);

        // 요청의 source 가 MANUAL 이어도 인식 결과가 있으면 사진 경로다
        service.create(userId, request().recognitionId(recognitionId.toString()).build());

        assertThat(saved.getValue().getRecognizedRaw()).isEqualTo("{\"readText\":\"GREEN TEA\"}");
        assertThat(saved.getValue().getSource()).isEqualTo(RegistrationSource.PHOTO);
    }

    @Test
    void 만료되거나_남의_인식_결과면_RECOGNITION_NOT_FOUND이고_저장하지_않는다() {
        givenProduct();
        givenNotUsing();
        UUID recognitionId = UUID.randomUUID();
        given(photoRecognitionService.getUsable(userId, recognitionId))
                .willThrow(new BusinessException(ErrorCode.RECOGNITION_NOT_FOUND));

        assertThatThrownBy(() -> service.create(userId, request().recognitionId(recognitionId.toString()).build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.RECOGNITION_NOT_FOUND);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 인식ID_형식이_틀리면_RECOGNITION_NOT_FOUND다() {
        givenProduct();
        givenNotUsing();

        assertThatThrownBy(() -> service.create(userId, request().recognitionId("rc_5f1a").build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.RECOGNITION_NOT_FOUND);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 없는_제품이면_PRODUCT_NOT_FOUND다() {
        given(productRepository.findById(productId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.create(userId, request().build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.PRODUCT_NOT_FOUND);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 같은_제품을_이미_쓰는_중이면_ALREADY_REGISTERED다() {
        givenProduct();
        given(userProductRepository.existsByUserIdAndProductIdAndUsageType(userId, productId, UsageType.USING))
                .willReturn(true);

        assertThatThrownBy(() -> service.create(userId, request().build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.ALREADY_REGISTERED);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 예전에_다_쓴_제품은_다시_등록하면_새_행을_넣고_예전_행은_건드리지_않는다() {
        // 쓰는 중인 행만 막는다. 다 쓴 행이 있어도 확인은 USING 으로만 한다
        givenProduct();
        givenNotUsing();
        ArgumentCaptor<UserProduct> saved = givenSave();

        service.create(userId, request().build());

        assertThat(saved.getValue().getId()).isEqualTo(userProductId);
        verify(userProductRepository, never()).existsByUserIdAndProductIdAndUsageType(userId, productId, UsageType.USED);
        verify(userProductRepository, never()).delete(any());
        verify(userProductRepository, never()).deleteById(any());
    }

    @Test
    void 동시에_같은_제품이_먼저_등록되면_ALREADY_REGISTERED다() {
        givenProduct();
        givenNotUsing();
        given(userProductRepository.saveAndFlush(any())).willThrow(new DataIntegrityViolationException("dup",
                new SQLException("duplicate key value violates unique constraint \"user_products_active_once\"")));

        assertThatThrownBy(() -> service.create(userId, request().build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.ALREADY_REGISTERED);
    }

    @Test
    void 다른_제약_위반은_그대로_던진다() {
        givenProduct();
        givenNotUsing();
        given(userProductRepository.saveAndFlush(any())).willThrow(new DataIntegrityViolationException("fk",
                new SQLException("violates foreign key constraint \"user_products_user_id_fkey\"")));

        assertThatThrownBy(() -> service.create(userId, request().build()))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
