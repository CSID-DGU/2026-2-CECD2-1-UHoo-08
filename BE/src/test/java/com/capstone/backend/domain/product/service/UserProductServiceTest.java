package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.request.UserProductUpdateRequest;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.dto.response.UserProductListResponse;
import com.capstone.backend.domain.product.dto.response.UserProductListResponse.Item;
import com.capstone.backend.domain.product.dto.response.UserProductUpdateResponse;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.enums.RegistrationSource;
import com.capstone.backend.domain.product.enums.ReplaceStatus;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.enums.UserProductFilter;
import com.capstone.backend.domain.product.enums.UserProductSort;
import com.capstone.backend.domain.product.enums.UserProductStatus;
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
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.List;
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
    // 보유 제품 목록

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 1);

    private final Product serum = Product.builder().id(UUID.randomUUID()).name("세럼").brand("A").category("skincare").imageUrl("https://img/s").build();
    private final Product lip = Product.builder().id(UUID.randomUUID()).name("립").brand("B").category("lip").build();

    private UserProduct row(Product product, UsageType usageType, LocalDate openedAt, LocalDate expiryDate,
                            LocalDateTime createdAt) {
        return UserProduct.builder().id(UUID.randomUUID()).userId(userId).productId(product.getId())
                .usageType(usageType).openedAt(openedAt).expiryDate(expiryDate).remainingPct(50)
                .createdAt(createdAt).build();
    }

    private void givenRows(List<UsageType> usageTypes, List<UserProduct> rows) {
        given(userProductRepository.findByUserIdAndUsageTypeIn(userId, usageTypes)).willReturn(rows);
        given(productRepository.findAllById(any())).willReturn(List.of(serum, lip));
    }

    @Test
    void 교체_필요도순은_기한_지남_곧_교체_괜찮음_순이고_같은_상태는_경과_비율이_큰_순이다() {
        LocalDateTime created = LocalDateTime.of(2026, 1, 1, 0, 0);
        UserProduct ok = row(serum, UsageType.USING, LocalDate.of(2026, 9, 1), LocalDate.of(2027, 9, 1), created);
        UserProduct expired = row(serum, UsageType.USING, LocalDate.of(2025, 1, 1), LocalDate.of(2026, 9, 1), created);
        UserProduct soonLess = row(lip, UsageType.USING, LocalDate.of(2026, 8, 1), LocalDate.of(2026, 11, 1), created);
        UserProduct soonMore = row(lip, UsageType.USING, LocalDate.of(2026, 1, 1), LocalDate.of(2026, 11, 1), created);
        givenRows(List.of(UsageType.USING), List.of(ok, expired, soonLess, soonMore));

        UserProductListResponse response = service.list(userId, UserProductFilter.USING, UserProductSort.REPLACE_NEED, 1, 20, TODAY);

        assertThat(response.getItems()).extracting(Item::getUserProductId)
                .containsExactly(expired.getId(), soonMore.getId(), soonLess.getId(), ok.getId());
        assertThat(response.getItems()).extracting(Item::getReplaceStatus).containsExactly(
                ReplaceStatus.EXPIRED, ReplaceStatus.SOON, ReplaceStatus.SOON, ReplaceStatus.OK);
        assertThat(response.getTotal()).isEqualTo(4);
        assertThat(response.getConflictSummary().getAvoidCount()).isZero();
        assertThat(response.getConflictSummary().getText()).isNull();
    }

    @Test
    void 항목에는_제품_정보와_교체_시기가_들어간다() {
        UserProduct expired = row(serum, UsageType.USING, LocalDate.of(2025, 1, 1), LocalDate.of(2026, 9, 17), LocalDateTime.of(2025, 1, 1, 0, 0));
        givenRows(List.of(UsageType.USING), List.of(expired));

        Item item = service.list(userId, UserProductFilter.USING, UserProductSort.REPLACE_NEED, 1, 20, TODAY).getItems().get(0);

        assertThat(item.getProductId()).isEqualTo(serum.getId());
        assertThat(item.getName()).isEqualTo("세럼");
        assertThat(item.getBrand()).isEqualTo("A");
        assertThat(item.getImageUrl()).isEqualTo("https://img/s");
        assertThat(item.getOpenedAt()).isEqualTo(LocalDate.of(2025, 1, 1));
        assertThat(item.getRemainingPct()).isEqualTo(50);
        assertThat(item.getReplaceProgress()).isEqualTo(100);
        assertThat(item.getReplaceText()).isEqualTo("기한이 2주 지났어요");
        assertThat(item.getConflictText()).isNull();
    }

    @Test
    void 최근순은_최근에_등록한_순이다() {
        UserProduct older = row(serum, UsageType.USING, null, null, LocalDateTime.of(2026, 1, 1, 0, 0));
        UserProduct newer = row(lip, UsageType.USING, null, null, LocalDateTime.of(2026, 9, 1, 0, 0));
        givenRows(List.of(UsageType.USING), List.of(older, newer));

        UserProductListResponse response = service.list(userId, UserProductFilter.USING, UserProductSort.RECENT, 1, 20, TODAY);

        assertThat(response.getItems()).extracting(Item::getUserProductId).containsExactly(newer.getId(), older.getId());
    }

    @Test
    void 다_쓴_제품은_다_쓴_행과_버린_행을_함께_읽고_같은_제품의_여러_통이_각각_나온다() {
        LocalDateTime created = LocalDateTime.of(2026, 1, 1, 0, 0);
        UserProduct firstBottle = row(serum, UsageType.USED, LocalDate.of(2025, 1, 1), null, created);
        UserProduct secondBottle = row(serum, UsageType.USED, LocalDate.of(2025, 7, 1), null, created.plusDays(1));
        UserProduct discarded = row(lip, UsageType.DISCARDED, LocalDate.of(2026, 1, 1), null, created.plusDays(2));
        givenRows(List.of(UsageType.USED, UsageType.DISCARDED), List.of(firstBottle, secondBottle, discarded));

        UserProductListResponse response = service.list(userId, UserProductFilter.FINISHED, UserProductSort.RECENT, 1, 20, TODAY);

        assertThat(response.getItems()).extracting(Item::getUserProductId)
                .containsExactly(discarded.getId(), secondBottle.getId(), firstBottle.getId());
    }

    @Test
    void 페이지는_1부터_세고_전체_개수는_자르기_전_개수다() {
        LocalDateTime created = LocalDateTime.of(2026, 1, 1, 0, 0);
        List<UserProduct> rows = List.of(
                row(serum, UsageType.USING, null, null, created.plusDays(3)),
                row(serum, UsageType.USING, null, null, created.plusDays(2)),
                row(lip, UsageType.USING, null, null, created.plusDays(1)));
        givenRows(List.of(UsageType.USING), rows);

        UserProductListResponse page2 = service.list(userId, UserProductFilter.USING, UserProductSort.RECENT, 2, 2, TODAY);

        assertThat(page2.getItems()).extracting(Item::getUserProductId).containsExactly(rows.get(2).getId());
        assertThat(page2.getTotal()).isEqualTo(3);
    }

    @Test
    void 개봉일이_없는_예전_행은_구매일_그다음_등록일을_시작일로_쓴다() {
        UserProduct purchased = UserProduct.builder().purchasedAt(LocalDate.of(2026, 2, 1))
                .createdAt(LocalDateTime.of(2026, 3, 1, 9, 0)).build();
        UserProduct createdOnly = UserProduct.builder().createdAt(LocalDateTime.of(2026, 3, 1, 9, 0)).build();

        assertThat(UserProductService.startedAt(purchased)).isEqualTo(LocalDate.of(2026, 2, 1));
        assertThat(UserProductService.startedAt(createdOnly)).isEqualTo(LocalDate.of(2026, 3, 1));
    }
    // 보유 제품 수정

    private UserProduct mine(UsageType usageType) {
        return UserProduct.builder().id(userProductId).userId(userId).productId(productId)
                .usageType(usageType).openedAt(LocalDate.of(2026, 1, 1)).remainingPct(70)
                .createdAt(LocalDateTime.of(2026, 1, 1, 0, 0)).build();
    }

    private UserProduct givenMine(UsageType usageType) {
        UserProduct row = mine(usageType);
        given(userProductRepository.findById(userProductId)).willReturn(Optional.of(row));
        given(userProductRepository.saveAndFlush(row)).willReturn(row);
        return row;
    }

    @Test
    void 잔량만_보내면_잔량만_바뀌고_상태와_다른_값은_그대로다() {
        UserProduct row = givenMine(UsageType.USING);

        UserProductUpdateResponse response = service.update(userId, userProductId,
                UserProductUpdateRequest.builder().remainingPct(40).build(), TODAY);

        assertThat(response.getUserProductId()).isEqualTo(userProductId);
        assertThat(response.getStatus()).isEqualTo(UserProductStatus.USING);
        assertThat(response.getRemainingPct()).isEqualTo(40);
        assertThat(row.getOpenedAt()).isEqualTo(LocalDate.of(2026, 1, 1));
        assertThat(row.getFinishedAt()).isNull();
        assertThat(row.getUpdatedAt()).isNotNull();
    }

    @Test
    void 기한_정보는_보낸_것만_바뀐다() {
        UserProduct row = givenMine(UsageType.USING);

        service.update(userId, userProductId, UserProductUpdateRequest.builder()
                .expiryDate(LocalDate.of(2027, 4, 18)).paoMonths(12).build(), TODAY);

        assertThat(row.getExpiryDate()).isEqualTo(LocalDate.of(2027, 4, 18));
        assertThat(row.getPaoMonths()).isEqualTo(12);
        assertThat(row.getOpenedAt()).isEqualTo(LocalDate.of(2026, 1, 1));
        assertThat(row.getRemainingPct()).isEqualTo(70);
    }

    @Test
    void 모두_사용은_다_쓴_날을_오늘로_두고_잔량을_0으로_한다() {
        UserProduct row = givenMine(UsageType.USING);

        UserProductUpdateResponse response = service.update(userId, userProductId,
                UserProductUpdateRequest.builder().status(UserProductStatus.FINISHED).build(), TODAY);

        assertThat(response.getStatus()).isEqualTo(UserProductStatus.FINISHED);
        assertThat(response.getRemainingPct()).isZero();
        assertThat(row.getUsageType()).isEqualTo(UsageType.USED);
        assertThat(row.getFinishedAt()).isEqualTo(TODAY);
    }

    @Test
    void 진작_다_씀은_고른_날을_다_쓴_날로_둔다() {
        UserProduct row = givenMine(UsageType.USING);

        service.update(userId, userProductId, UserProductUpdateRequest.builder()
                .status(UserProductStatus.FINISHED).finishedAt(LocalDate.of(2026, 9, 10)).remainingPct(30).build(), TODAY);

        assertThat(row.getFinishedAt()).isEqualTo(LocalDate.of(2026, 9, 10));
        // 다 쓴 제품은 남은 양이 없다
        assertThat(row.getRemainingPct()).isZero();
    }

    @Test
    void 이미_다_쓴_제품은_다_쓴_날만_고칠_수_있다() {
        UserProduct row = givenMine(UsageType.USED);
        row.finish(LocalDate.of(2026, 9, 1));

        service.update(userId, userProductId,
                UserProductUpdateRequest.builder().finishedAt(LocalDate.of(2026, 8, 1)).build(), TODAY);

        assertThat(row.getUsageType()).isEqualTo(UsageType.USED);
        assertThat(row.getFinishedAt()).isEqualTo(LocalDate.of(2026, 8, 1));
    }

    @Test
    void 쓰는_중인_제품에_다_쓴_날만_오면_무시한다() {
        UserProduct row = givenMine(UsageType.USING);

        service.update(userId, userProductId,
                UserProductUpdateRequest.builder().finishedAt(LocalDate.of(2026, 8, 1)).build(), TODAY);

        assertThat(row.getUsageType()).isEqualTo(UsageType.USING);
        assertThat(row.getFinishedAt()).isNull();
    }

    @Test
    void 버림으로_바꾼다() {
        UserProduct row = givenMine(UsageType.USING);

        UserProductUpdateResponse response = service.update(userId, userProductId,
                UserProductUpdateRequest.builder().status(UserProductStatus.DISCARDED).build(), TODAY);

        assertThat(response.getStatus()).isEqualTo(UserProductStatus.DISCARDED);
        assertThat(row.getUsageType()).isEqualTo(UsageType.DISCARDED);
    }

    @Test
    void 다_씀을_되돌리면_쓰는_중이_되고_다_쓴_날을_비운다() {
        UserProduct row = givenMine(UsageType.USED);
        row.finish(LocalDate.of(2026, 9, 1));
        given(userProductRepository.existsByUserIdAndProductIdAndUsageTypeAndIdNot(
                userId, productId, UsageType.USING, userProductId)).willReturn(false);

        UserProductUpdateResponse response = service.update(userId, userProductId,
                UserProductUpdateRequest.builder().status(UserProductStatus.USING).remainingPct(60).build(), TODAY);

        assertThat(response.getStatus()).isEqualTo(UserProductStatus.USING);
        assertThat(response.getRemainingPct()).isEqualTo(60);
        assertThat(row.getFinishedAt()).isNull();
    }

    @Test
    void 되돌릴_때_같은_제품을_쓰는_중인_다른_통이_있으면_ALREADY_REGISTERED다() {
        UserProduct row = mine(UsageType.USED);
        given(userProductRepository.findById(userProductId)).willReturn(Optional.of(row));
        given(userProductRepository.existsByUserIdAndProductIdAndUsageTypeAndIdNot(
                userId, productId, UsageType.USING, userProductId)).willReturn(true);

        assertThatThrownBy(() -> service.update(userId, userProductId,
                UserProductUpdateRequest.builder().status(UserProductStatus.USING).build(), TODAY))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.ALREADY_REGISTERED);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 이미_쓰는_중인_제품을_쓰는_중으로_보내면_확인_없이_그대로다() {
        UserProduct row = givenMine(UsageType.USING);

        service.update(userId, userProductId,
                UserProductUpdateRequest.builder().status(UserProductStatus.USING).build(), TODAY);

        assertThat(row.getUsageType()).isEqualTo(UsageType.USING);
        verify(userProductRepository, never()).existsByUserIdAndProductIdAndUsageTypeAndIdNot(any(), any(), any(), any());
    }

    @Test
    void 남의_보유_제품을_수정하면_USER_PRODUCT_NOT_FOUND다() {
        UserProduct others = UserProduct.builder().id(userProductId).userId(UUID.randomUUID()).productId(productId)
                .usageType(UsageType.USING).build();
        given(userProductRepository.findById(userProductId)).willReturn(Optional.of(others));

        assertThatThrownBy(() -> service.update(userId, userProductId,
                UserProductUpdateRequest.builder().remainingPct(10).build(), TODAY))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.USER_PRODUCT_NOT_FOUND);
        verify(userProductRepository, never()).saveAndFlush(any());
    }

    @Test
    void 없는_보유_제품을_수정하면_USER_PRODUCT_NOT_FOUND다() {
        given(userProductRepository.findById(userProductId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.update(userId, userProductId,
                UserProductUpdateRequest.builder().remainingPct(10).build(), TODAY))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.USER_PRODUCT_NOT_FOUND);
    }
}
